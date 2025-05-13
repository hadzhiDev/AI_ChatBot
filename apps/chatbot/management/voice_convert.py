import json
import requests

def handle(data):
    data = json.loads(data)
    voice_url = data.get("voice_link")  # <-- читаем переменную, но не переопределяем её

    if not voice_url:
        return {
            "result": "Ссылка на голосовое сообщение не найдена."
        }

    try:
        # Скачиваем аудио по voice_url
        audio_response = requests.get(voice_url)
        if audio_response.status_code != 200:
            return {
                "result": "Не удалось скачать аудиофайл по ссылке."
            }

        # Сохраняем во временный файл
        with open("voice.ogg", "wb") as audio_file:
            audio_file.write(audio_response.content)

        # Подготовка запроса к OpenAI
        openai_api_key = "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"  # <-- вставь сюда свой OpenAI ключ

        headers = {
            "Authorization": f"Bearer {openai_api_key}"
        }

        files = {
            "file": open("voice.ogg", "rb"),
            "model": (None, "whisper-1")
        }

        transcription_response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers=headers,
            files=files
        )

        if transcription_response.status_code == 200:
            transcribed_text = transcription_response.json()["text"]
            return {"result": transcribed_text}
        else:
            return {
                "result": f"Ошибка от OpenAI: {transcription_response.text}"
            }

    except Exception as e:
        return {
            "result": f"Произошла ошибка: {str(e)}"
        }