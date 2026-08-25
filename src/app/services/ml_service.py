from src.app.ml.pipeline import predict_text

async def predict(payload: str) -> dict:
    y = predict_text(payload)
    return {"prediction": y}
