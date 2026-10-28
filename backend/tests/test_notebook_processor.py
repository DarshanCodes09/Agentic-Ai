"""
Tests for Jupyter Notebook parsing, extraction, execution auditing, and safety limits.
"""

import json
from app.services.document_processing.notebook_processor import (
    NotebookProcessor,
    get_notebook_processor,
)


def create_sample_notebook(cells=None, metadata=None):
    if cells is None:
        cells = []
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": metadata or {
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.12"
            }
        },
        "cells": cells
    }


def test_valid_executed_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": "# RNN & LSTM Classification\nThis assignment explores hyperparameter tuning."
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "source": "import numpy as np\nprint('Numpy loaded successfully')",
            "outputs": [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": "Numpy loaded successfully\n"
                }
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "source": "val_acc = 0.884\nval_acc",
            "outputs": [
                {
                    "output_type": "execute_result",
                    "execution_count": 2,
                    "data": {
                        "text/plain": "0.884"
                    },
                    "metadata": {}
                }
            ]
        }
    ]
    nb_dict = create_sample_notebook(cells)
    raw_json = json.dumps(nb_dict)

    processor = get_notebook_processor()
    parsed = processor.parse_content(raw_json)

    assert parsed.is_valid is True
    assert parsed.audit.total_cells == 3
    assert parsed.audit.code_cells == 2
    assert parsed.audit.executed_code_cells == 2
    assert parsed.audit.unexecuted_code_cells == 0
    assert parsed.audit.execution_status == "COMPLETE"
    assert parsed.audit.cells_with_errors == 0
    assert parsed.audit.execution_order_anomaly is False

    evidence_text = parsed.text_representation
    assert "RNN & LSTM Classification" in evidence_text
    assert "Numpy loaded successfully" in evidence_text
    assert "0.884" in evidence_text
    assert "COMPLETE" in evidence_text


def test_unexecuted_notebook():
    cells = [
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "source": "def train_model():\n    pass",
            "outputs": []
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "source": "result = train_model()",
            "outputs": []
        }
    ]
    raw_json = json.dumps(create_sample_notebook(cells))

    processor = get_notebook_processor()
    parsed = processor.parse_content(raw_json)

    assert parsed.is_valid is True
    assert parsed.audit.code_cells == 2
    assert parsed.audit.executed_code_cells == 0
    assert parsed.audit.unexecuted_code_cells == 2
    assert parsed.audit.execution_status == "UNEXECUTED"

    evidence_text = parsed.text_representation
    assert "UNEXECUTED" in evidence_text
    assert "lack saved execution outputs" in evidence_text


def test_notebook_with_runtime_error():
    cells = [
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "source": "import tensorflow as tf",
            "outputs": []
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "source": "model = tf.keras.models.Sequential()",
            "outputs": [
                {
                    "output_type": "error",
                    "ename": "AttributeError",
                    "evalue": "module 'tensorflow' has no attribute 'keras'",
                    "traceback": [
                        "Traceback (most recent call last):",
                        "  File '<stdin>', line 1, in <module>",
                        "AttributeError: module 'tensorflow' has no attribute 'keras'"
                    ]
                }
            ]
        }
    ]
    raw_json = json.dumps(create_sample_notebook(cells))

    processor = get_notebook_processor()
    parsed = processor.parse_content(raw_json)

    assert parsed.audit.cells_with_errors == 1
    assert parsed.audit.execution_status == "ERRORED"

    evidence_text = parsed.text_representation
    assert "RUNTIME ERROR" in evidence_text
    assert "AttributeError" in evidence_text


def test_non_linear_execution_order_anomaly():
    cells = [
        {
            "cell_type": "code",
            "execution_count": 10,
            "metadata": {},
            "source": "step_one = 10",
            "outputs": [{"output_type": "stream", "name": "stdout", "text": "10"}]
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "metadata": {},
            "source": "step_two = 3",
            "outputs": [{"output_type": "stream", "name": "stdout", "text": "3"}]
        }
    ]
    raw_json = json.dumps(create_sample_notebook(cells))

    processor = get_notebook_processor()
    parsed = processor.parse_content(raw_json)

    assert parsed.audit.execution_order_anomaly is True
    evidence_text = parsed.text_representation
    assert "non-linear" in evidence_text.lower() or "anomaly" in evidence_text.lower() or parsed.audit.execution_order_anomaly


def test_malformed_notebook_handling():
    invalid_json = "This is not JSON content at all"
    processor = get_notebook_processor()
    parsed = processor.parse_content(invalid_json)
    assert parsed.is_valid is False
    assert "Invalid JSON" in parsed.parse_error

    wrong_structure = json.dumps(["an", "array", "not", "object"])
    parsed2 = processor.parse_content(wrong_structure)
    assert parsed2.is_valid is False
    assert "Root is not a JSON object" in parsed2.parse_error


def test_representative_rnn_lstm_ml_assignment_notebook():
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": "# Hyperparameter Tuning of RNN and LSTM Networks for Sequence Classification\n"
                      "## 1. Dataset Preprocessing & Exploration\n"
                      "We preprocess IMDB sequences padding to maxlen=150."
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "source": "from tensorflow.keras.datasets import imdb\n"
                      "from tensorflow.keras.preprocessing import sequence\n"
                      "max_features = 10000\n"
                      "maxlen = 150\n"
                      "(X_train, y_train), (X_test, y_test) = imdb.load_data(num_words=max_features)\n"
                      "X_train = sequence.pad_sequences(X_train, maxlen=maxlen)\n"
                      "X_test = sequence.pad_sequences(X_test, maxlen=maxlen)\n"
                      "print(f'Train shape: {X_train.shape}, Test shape: {X_test.shape}')",
            "outputs": [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": "Train shape: (25000, 150), Test shape: (25000, 150)\n"
                }
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": "## 2. Baseline SimpleRNN Architecture"
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "source": "from tensorflow.keras.models import Sequential\n"
                      "from tensorflow.keras.layers import Embedding, SimpleRNN, Dense\n"
                      "model_rnn = Sequential([\n"
                      "    Embedding(10000, 64),\n"
                      "    SimpleRNN(64),\n"
                      "    Dense(1, activation='sigmoid')\n"
                      "])\n"
                      "model_rnn.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])\n"
                      "print('Baseline RNN compiled')",
            "outputs": [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": "Baseline RNN compiled\n"
                }
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": "## 3. LSTM Hyperparameter Tuning Grid Search"
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "metadata": {},
            "source": "results = []\n"
                      "for units in [32, 64, 128]:\n"
                      "    for dropout in [0.2, 0.5]:\n"
                      "        # Train and evaluate\n"
                      "        print(f'Tuned units={units}, dropout={dropout}')\n"
                      "results.append({'units': 64, 'dropout': 0.2, 'val_accuracy': 0.872})\n"
                      "import pandas as pd\n"
                      "df = pd.DataFrame(results)\n"
                      "print(df.to_string())",
            "outputs": [
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": "   units  dropout  val_accuracy\n0     64      0.2         0.872\n"
                }
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": "## 4. Discussion & Learning Curves Analysis\n"
                      "LSTM significantly mitigated vanishing gradient and outperformed SimpleRNN."
        }
    ]
    nb_dict = create_sample_notebook(cells)
    raw_json = json.dumps(nb_dict)

    processor = get_notebook_processor()
    parsed = processor.parse_content(raw_json)

    assert parsed.audit.total_cells == 7
    assert parsed.audit.code_cells == 3
    assert parsed.audit.executed_code_cells == 3
    assert parsed.audit.execution_status == "COMPLETE"
    assert parsed.audit.cells_with_errors == 0

    evidence = parsed.text_representation
    assert "Hyperparameter Tuning of RNN and LSTM" in evidence
    assert "Train shape: (25000, 150)" in evidence
    assert "Baseline SimpleRNN Architecture" in evidence
    assert "val_accuracy" in evidence
    assert "0.872" in evidence
