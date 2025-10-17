import pandas as pd
from sklearn.linear_model import LinearRegression

def predict_tomorrow(df: pd.DataFrame) -> int:
    df = df.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    df['day_num'] = (df['Date'] - df['Date'].min()).dt.days
    df['is_weekend'] = df['Date'].dt.weekday.isin([5,6]).astype(int)
    if len(df) <= 1: return 0
    X = df[['day_num', 'is_weekend']]
    y = df['Steps']
    model = LinearRegression()
    model.fit(X, y)
    next_day = df['day_num'].max() + 1
    next_is_weekend = ((df['Date'].max() + pd.Timedelta(days=1)).weekday() in [5,6])
    return int(model.predict([[next_day, int(next_is_weekend)]])[0])
