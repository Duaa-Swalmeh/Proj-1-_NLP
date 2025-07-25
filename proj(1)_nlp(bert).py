# -*- coding: utf-8 -*-
"""Proj(1)_NLP(BERT).ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1T5Oz0YLVEt5bpegMFqk-u655Agy-nMvz

Fine-tuning DistilBERT with LoRA (PEFT)
"""

import pandas as pd
data=pd.read_csv("/content/cellula toxic data  (1).csv")
from sklearn.utils import resample
max_count = data['Toxic Category'].value_counts().max()


balanced_data = pd.concat([
    resample(data[data['Toxic Category'] == label],
             replace=True,
             n_samples=max_count,
             random_state=42)
    for label in data['Toxic Category'].unique()
])


balanced_data = balanced_data.sample(frac=1, random_state=42).reset_index(drop=True)


print(balanced_data['Toxic Category'].value_counts())

import nltk
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('omw-1.4')
nltk.download('all')
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
import re

!pip install transformers datasets peft accelerate bitsandbytes

!pip install evaluate

from sklearn.preprocessing import LabelEncoder

stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def preprocess_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    tokens = word_tokenize(text)
    filtered_tokens = [w for w in tokens if w not in stop_words]
    lemmatized_tokens = [lemmatizer.lemmatize(w) for w in filtered_tokens]
    return ' '.join(lemmatized_tokens)

data['clean_text'] = data['query'].apply(preprocess_text)


le = LabelEncoder()
data['label_encoded'] = le.fit_transform(data['Toxic Category'])
num_classes = len(le.classes_)

from sklearn.model_selection import train_test_split
from datasets import Dataset

train_df, test_df = train_test_split(data, test_size=0.2, stratify=data['label_encoded'], random_state=42)
train_df, val_df = train_test_split(train_df, test_size=0.1, stratify=train_df['label_encoded'], random_state=42)


train_dataset = Dataset.from_pandas(train_df)
val_dataset = Dataset.from_pandas(val_df)
test_dataset = Dataset.from_pandas(test_df)

from transformers import DistilBertTokenizerFast

tokenizer = DistilBertTokenizerFast.from_pretrained('distilbert-base-uncased')

def tokenize_function(examples):
    return tokenizer(examples['clean_text'], padding='max_length', truncation=True, max_length=128)

tokenized_train = train_dataset.map(tokenize_function, batched=True)
tokenized_val = val_dataset.map(tokenize_function, batched=True)
tokenized_test = test_dataset.map(tokenize_function, batched=True)


tokenized_train = tokenized_train.rename_column("label_encoded", "labels")
tokenized_val = tokenized_val.rename_column("label_encoded", "labels")
tokenized_test = tokenized_test.rename_column("label_encoded", "labels")


tokenized_train.set_format('torch', columns=['input_ids', 'attention_mask', 'labels'])
tokenized_val.set_format('torch', columns=['input_ids', 'attention_mask', 'labels'])
tokenized_test.set_format('torch', columns=['input_ids', 'attention_mask', 'labels'])

!pip install numpy==1.26.4 --force-reinstall

import numpy as np
from transformers import DistilBertForSequenceClassification, TrainingArguments, Trainer
from peft import get_peft_model, LoraConfig, TaskType
import evaluate
import torch
from sklearn.metrics import classification_report

model = DistilBertForSequenceClassification.from_pretrained("distilbert-base-uncased", num_labels=num_classes)

lora_config = LoraConfig(
    task_type=TaskType.SEQ_CLS,
    inference_mode=False,
    r=8,
    lora_alpha=16,
    lora_dropout=0.1,
    target_modules=["q_lin", "v_lin"]
)

model = get_peft_model(model, lora_config)

training_args = TrainingArguments(
    output_dir="./bert_results",
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=3,
    weight_decay=0.01,
    logging_dir='./logs',
    logging_steps=50,
)

accuracy = evaluate.load("accuracy")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = torch.argmax(torch.tensor(logits), dim=-1)
    return accuracy.compute(predictions=predictions, references=labels)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_val,
    compute_metrics=compute_metrics
)

trainer.train()

print("\nPerformance of DistilBERT (LoRA) Model:")
predictions = trainer.predict(tokenized_test)
y_pred_bert = np.argmax(predictions.predictions, axis=1)
y_test = tokenized_test['labels'].numpy()
print(classification_report(y_test, y_pred_bert, target_names=le.classes_))

import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix

plt.figure(figsize=(10, 8))
sns.heatmap(confusion_matrix(y_test, y_pred_bert), annot=True, fmt='d',
            xticklabels=le.classes_, yticklabels=le.classes_, cmap="Greens")
plt.title("Confusion Matrix - DistilBERT (LoRA)")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.show()