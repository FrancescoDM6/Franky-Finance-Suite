"""Train a lightweight TF-IDF + LinearSVM sentiment model.

Uses the Twitter Financial News Sentiment dataset for training.
Includes hyperparameter tuning via GridSearchCV for better accuracy.
Outputs a trained model to phinan/data/sentiment_model.joblib

Usage:
    python scripts/train_sentiment_model.py
"""

import logging
import os
import warnings

import joblib
import numpy as np
import pandas as pd
from datasets import load_dataset
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Configuration
MODEL_PATH = "phinan/data/sentiment_model.joblib"
DATASET_NAME = "zeroshot/twitter-financial-news-sentiment"

def train():
    logger.info("Loading dataset: %s...", DATASET_NAME)
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
        
        logger.info("Loaded %s examples.", len(df))
        
        X = df["text"]
        y = df["label"]

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info("Training model with GridSearch (SVM)...")
        
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

        logger.info("Best params: %s", grid_search.best_params_)
        best_model = grid_search.best_estimator_

        # Evaluate
        logger.info("\nEvaluating best model...")
        y_pred = best_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info("Accuracy: %.4f", accuracy)
        logger.info("\nClassification Report:")
        logger.info(
            classification_report(
                y_test,
                y_pred,
                target_names=["Negative", "Neutral", "Positive"],
            )
        )

        # Save
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(best_model, MODEL_PATH)
        logger.info("\nModel saved to %s", MODEL_PATH)
        
    except Exception as e:
        import sys
        logger.exception("Error during training: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    train()
