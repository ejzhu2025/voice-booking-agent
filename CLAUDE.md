# Voice Booking Agent (Ringo)

Bonchon餐厅AI电话预订系统，Gemini Live API实现实时语音对话。

## 技术栈
- **后端**: FastAPI + Gemini Live API（STT+LLM+TTS原生）+ Twilio + Square
- **部署**: Google Cloud Run，region us-central1

## 关键配置
- **Live模型**: `gemini-2.5-flash-native-audio-latest`（支持barge-in打断）
- **❌ 不能用**: `gemini-2.0-flash-live-001`（这个model ID会404）
- **Chat模型**: `gemini-2.0-flash`（text demo endpoint用）
- **音频桥**: Twilio mulaw 8kHz ↔ audioop ↔ Gemini PCM 16kHz/24kHz

## Endpoints
- `POST /incoming-call` — Twilio webhook
- `WS /media-stream` — 音频桥
- `POST /demo/chat` — 文字demo

## 部署流程（每次更新必须遵守）
1. 数据库变更用Alembic迁移，只加列不删/改列
2. API路由加版本前缀 `/api/v1/`
3. Cloud Run滚动发布：先10%流量观察30分钟，再切100%
```bash
gcloud run deploy ringo --image gcr.io/.../ringo:v2 --no-traffic
gcloud run services update-traffic ringo --to-revisions v2=10,v1=90
```

## 踩过的坑
- Gemini Live模型名非常重要，用错就404，必须用`gemini-2.5-flash-native-audio-latest`
- 音频采样率转换不能省，Twilio是8kHz mulaw，Gemini要16kHz PCM

## UI规范
- 不用emoji，用SVG图标，暗金科技风格

## 当前状态
- Hackathon提交完成（Gemini Live Agent Challenge, 2026-03-16截止）
