"""Train a lightweight TF-IDF + LinearSVM sentiment model.

Uses the Twitter Financial News Sentiment dataset for training.
Includes hyperparameter tuning via GridSearchCV for better accuracy.
Outputs a trained model to phinan/data/sentiment_model.joblib

Usage:
    python scripts/train_sentiment_model.py
"""

import os
import joblib
import numpy as np
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, accuracy_score
import pandas as pd
import warnings

# Configuration
MODEL_PATH = "phinan/data/sentiment_model.joblib"
DATASET_NAME = "zeroshot/twitter-financial-news-sentiment"

def train():
    print(f"Loading dataset: {DATASET_NAME}...")
    try:
        # Load dataset
        dataset = load_dataset(DATASET_NAME)
        
        # Combine train and validation for more data
        train_df = dataset["train"].to_pandas()
        val_df = dataset["validation"].to_pandas()
        
        df = pd.concat([train_df, val_df], ignore_index=True)
        
        # Labels: 0=Bearish (negative), 1=Bullish (positive), 2=Neutral
        # Map to our standard: 0=negative, 1=neutral, 2=positive
        label_map = {0: 0, 1: 2, 2: 1}  
        df["label"] = df["label"].map(label_map)
        
        print(f"Loaded {len(df)} examples.")
        
        X = df["text"]
        y = df["label"]

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print("Training model with GridSearch (SVM)...")
        
        # Pipeline: TF-IDF -> LinearSVC (calibrated for probabilities)
        # We need CalibratedClassifierCV because LinearSVC does not support predict_proba by default
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(stop_words="english")),
            ("clf", CalibratedClassifierCV(LinearSVC(class_weight="balanced", dual="auto"), method="sigmoid"))
        ])

        # Hyperparameter grid
        param_grid = {
            "tfidf__ngram_range": [(1, 1), (1, 2)],
            "tfidf__max_features": [5000, 10000, 20000],
        }
        # Note: CalibratedClassifierCV wraps the estimator, so we tune the inner estimator params if needed,
        # but Tfidf tuning is usually most impactful for text. 
        # Tuning inner SVM C-value is tricky with CalibratedCV in simple grid syntax, keeping it defaults.

        grid_search = GridSearchCV(
            pipeline, 
            param_grid, 
            cv=3, 
            n_jobs=1,  # Set to 1 to avoid Windows multiprocessing errors
            verbose=1,
            scoring="accuracy"
        )

        grid_search.fit(X_train, y_train)

        print(f"Best params: {grid_search.best_params_}")
        best_model = grid_search.best_estimator_

        # Evaluate
        print("\nEvaluating best model...")
        y_pred = best_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Accuracy: {accuracy:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, target_names=["Negative", "Neutral", "Positive"]))

        # Save
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(best_model, MODEL_PATH)
        print(f"\nModel saved to {MODEL_PATH}")
        
    except Exception as e:
        import traceback
        import sys
        print(f"Error during training: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    train()
