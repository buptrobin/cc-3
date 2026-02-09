#!/bin/bash

echo "正在停止旧服务..."

# 查找并停止占用端口的进程
for port in 3001 8001 5173; do
    pid=$(netstat -ano | grep ":$port" | grep LISTENING | awk '{print $5}' | head -1)
    if [ ! -z "$pid" ]; then
        echo "停止端口 $port 的进程 (PID: $pid)"
        taskkill //PID $pid //F 2>/dev/null
    fi
done

echo "等待端口释放..."
sleep 2

