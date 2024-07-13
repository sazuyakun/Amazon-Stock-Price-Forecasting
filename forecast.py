# -*- coding: utf-8 -*-
"""Untitled2.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1wzGQXlCiyI8358ldlDuL_Oc1NO_qOkMK

## Importing Libraries
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

"""## Data and preprocessing"""

df = pd.read_csv('/content/AMZN.csv')

df.head()

## We only need the closing values and the date
df = df[['Date', 'Close']]
df.head()

df['Date'] = pd.to_datetime(df['Date'])

plt.plot(df['Date'], df['Close'])

from copy import deepcopy as dc
def prepare_df_for_lstm(df, n_steps):
    df = dc(df)

    df.set_index('Date', inplace=True)

    for i in range(1, n_steps+1):
        df[f'Close(t-{i})'] = df['Close'].shift(i)

    df.dropna(inplace=True)

    return df

lookback = 7
shifted_df = prepare_df_for_lstm(df, lookback)
shifted_df.head()

X = shifted_df.iloc[:, 1:].values
y = shifted_df.iloc[:, 0].values

from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler(feature_range=(-1,1))
X = scaler.fit_transform(X)
y = scaler.fit_transform(y.reshape(-1,1))

X

X = dc(np.flip(X, axis=1)) ## Flipping for LSTM

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

X_train.shape, X_test.shape, y_train.shape, y_test.shape

"""## Data class"""

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
device

class TimeSeriesDataset(Dataset):
    def __init__(self, X, y):
        self.X = X.reshape(-1, lookback, 1)
        self.y = y.reshape(-1, 1)

        self.X = torch.tensor(self.X).float().to(device)
        self.y = torch.tensor(self.y).float().to(device)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

train_data = TimeSeriesDataset(X_train, y_train)
test_data = TimeSeriesDataset(X_test, y_test)

batch_size = 16
train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=False)

"""## Model Making"""

class ForecastingModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_stacked_layers):
        super().__init__()

        self.hidden_size = hidden_size
        self.num_stacked_layers = num_stacked_layers

        self.lstm = nn.LSTM(
            input_size,
            hidden_size,
            num_stacked_layers,
            batch_first=True
        )

        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        batch_size = x.size(0)
        h0 = torch.zeros(self.num_stacked_layers, batch_size, self.hidden_size).to(device)
        c0 = torch.zeros(self.num_stacked_layers, batch_size, self.hidden_size).to(device)

        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])

        return out

model = ForecastingModel(1, 64, 2)
model.to(device)
model

learning_rate = 0.001
num_epochs = 10
loss_fn = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

from tqdm import tqdm

for epoch in range(num_epochs):
    model.train()
    print(f"Epoch: {epoch + 1}")
    training_loss = 0.0

    for batch_idx, (X, y) in enumerate(tqdm(train_loader)):
        y_pred = model(X)
        loss = loss_fn(y_pred, y)

        # Optimizer compulse
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        training_loss += loss.item()

    print(f"Training loss: {training_loss/len(train_loader)}")

    model.eval()
    testing_loss = 0.0
    for batch_idx, (X, y) in enumerate(tqdm(test_loader)):
        with torch.inference_mode():
            output = model(X)
            loss = loss_fn(output, y)

            testing_loss += loss.item()

    print(f"Testing loss: {testing_loss/len(test_loader)}")
    print("...")

def data_to_lstm(X):
    X = X.reshape(-1, lookback, 1)
    X = torch.tensor(X).float().to(device)
    return X

with torch.no_grad():
    predicted = model(data_to_lstm(X_test)).to('cpu').numpy()

plt.plot(y_test, label='Actual')
plt.plot(predicted, label='Predicted')
plt.xlabel('Day')
plt.ylabel('Close')
plt.legend()
plt.show()

"""## Saving the model"""

PATH = "/content/model.pth"
torch.save(model.state_dict(), PATH)