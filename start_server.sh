#!/bin/bash
# 启动本地 HTTP 服务器，用于提供 .ics 文件

cd ~/.iflow-tasks-calendar

# 检查是否已有服务器在运行
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ 服务器已在运行 (http://localhost:8080)"
else
    echo "🚀 启动服务器..."
    # 使用 Python 3 启动 HTTP 服务器
    python3 -m http.server 8080 > /tmp/tasks-calendar-server.log 2>&1 &
    echo $! > /tmp/tasks-calendar-server.pid
    sleep 2
    
    if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "✅ 服务器已启动: http://localhost:8080/tasks_calendar.ics"
    else
        echo "❌ 服务器启动失败"
        cat /tmp/tasks-calendar-server.log
    fi
fi
