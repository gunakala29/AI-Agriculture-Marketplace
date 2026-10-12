import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import joblib

# Sample agricultural data
data = {
    "temperature": [20, 25, 30, 35, 22, 28, 32, 24],
    "humidity": [80, 70, 60, 50, 85, 65, 55, 75],
    "rainfall": [200, 150, 100, 80, 220, 120, 90, 180],
    "crop": [
        "Rice", "Rice", "Cotton", "Cotton",
        "Rice", "Maize", "Maize", "Rice"
    ]
}

df = pd.DataFrame(data)

X = df[["temperature", "humidity", "rainfall"]]
y = df["crop"]

model = DecisionTreeClassifier(random_state=42)

model.fit(X, y)

joblib.dump(model, "models/crop_model.pkl")

print("Crop AI model created successfully!")