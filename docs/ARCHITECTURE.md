# Архитектура MVP

1. **Ingest** — нормализация аудио и загрузка в S3.
2. **ASR** — транскрипция через faster-whisper.
3. **Диаризация** — pyannote / VAD + кластеризация.
4. **LLM** — Gemini со строгой JSON-схемой.
5. **Scoring** — агрегирование метрик и финальные баллы.
6. **Storage** — Postgres + S3.
7. **CLI** — `scripts/analyze_call` запускает весь pipeline.
8. **Web** — Next.js админка.
