# QGIS Plugin Project

Project phát triển plugin cho QGIS, chạy với Claude Code trên model DeepSeek.

## Cấu hình đã có
- **DeepSeek API** qua `https://api.deepseek.com/anthropic` (model: `deepseek-v4-flash`, pro: `deepseek-v4-pro`)
- **API key** lưu trong macOS Keychain, được đọc qua `.claude/get-deepseek-key.sh`
- Nếu key hết hạn hoặc lỗi: chạy `./.claude/setup-deepseek-key.sh` rồi dán key mới

## Quy ước
- (Bổ sung khi bắt đầu viết plugin: cấu trúc thư mục, tên plugin, ngôn ngữ UI, v.v.)
