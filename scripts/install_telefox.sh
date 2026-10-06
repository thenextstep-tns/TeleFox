#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# 🦊 TeleFox: Автономный установщик для Android 14 (Realme 9 Pro+)
# ==============================================================================

set -e

echo ""
echo "============================================================"
echo "    🦊 УСТАНОВКА TELEFOX НА REALME 9 PRO+ (ANDROID 14)"
echo "============================================================"
echo ""

# 1. Активация удержания процессора (WakeLock) против Doze Mode
echo "[1/6] 🛡️ Активация защиты от засыпания процессора (WakeLock)..."
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "  [+] WakeLock активирован! Процессор Dimensity 920 не уснёт при выключенном экране."
else
    echo "  [!] Внимание: установите termux-api для полной интеграции с уведомлениями."
fi

# 2. Обновление пакетов и установка системных утилит
echo "[2/6] 📦 Установка необходимых пакетов (Python, Curl, API)..."
pkg update -y >/dev/null 2>&1 || true
pkg install -y python python-pip termux-api curl tar >/dev/null 2>&1

# 3. Подготовка рабочего каталога
INSTALL_DIR="$HOME/telefox"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 4. Скачивание готового пакета TeleFox (с сессией и конфигурацией)
PC_HOST="192.168.7.155:5050"
echo "[3/6] 📥 Скачивание автономного пакета TeleFox с сессией Telegram..."
curl -s -f "http://$PC_HOST/telefox/telefox-bundle.tar.gz" -o telefox-bundle.tar.gz || {
    echo "[!] Не удалось скачать с $PC_HOST. Введите IP адрес вашего компьютера:"
    read -r CUSTOM_IP
    PC_HOST="$CUSTOM_IP"
    curl -f "http://$PC_HOST/telefox/telefox-bundle.tar.gz" -o telefox-bundle.tar.gz
}

echo "[4/6] 📂 Распаковка исходного кода и сессии..."
tar -xzf telefox-bundle.tar.gz
rm -f telefox-bundle.tar.gz

# 5. Установка Python зависимостей
echo "[5/6] ⚙️ Установка библиотек Telethon, FastAPI, PyMongo..."
pip install --upgrade pip || true
pip install telethon pymongo motor fastapi uvicorn aiohttp python-dotenv beautifulsoup4 pydantic requests

# Создание исполняемой команды 'telefox' в системе
mkdir -p "$PREFIX/bin"
cat << 'EOF' > "$PREFIX/bin/telefox"
#!/data/data/com.termux/files/usr/bin/bash
cd "$HOME/telefox"
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi
echo "[*] Запуск TeleFox на телефоне..."
python main.py
EOF
chmod +x "$PREFIX/bin/telefox"

# Настройка автозапуска через Termux:Boot (если установлен)
BOOT_DIR="$HOME/.termux/boot"
mkdir -p "$BOOT_DIR"
cat << 'EOF' > "$BOOT_DIR/start-telefox.sh"
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd "$HOME/telefox"
python main.py > "$HOME/telefox/telefox_boot.log" 2>&1 &
EOF
chmod +x "$BOOT_DIR/start-telefox.sh"

echo "[6/6] 🚀 Запуск автономной службы TeleFox..."
# Проверка и остановка старого процесса, если был
pkill -f "python main.py" 2>/dev/null || true
nohup python main.py > "$HOME/telefox/telefox.log" 2>&1 &
sleep 3

# Отправка постоянного статусного уведомления в шторку Android 14
if command -v termux-notification >/dev/null 2>&1; then
    termux-notification \
        --id 9999 \
        --title "🦊 TeleFox: Автономный режим" \
        --content "Мониторинг Telegram активен 24/7 (Realme UI 5.0)" \
        --ongoing true \
        --priority low \
        --action "termux-open-url http://localhost:5050" 2>/dev/null || true
fi

# Открытие веб-интерфейса в мобильном браузере
if command -v termux-open-url >/dev/null 2>&1; then
    termux-open-url "http://localhost:5050" || true
fi

echo ""
echo "============================================================"
echo "    🎉 TELEFOX УСПЕШНО УСТАНОВЛЕН И ЗАПУЩЕН!"
echo "============================================================"
echo ""
echo "📱 Адрес приложения на телефоне: http://localhost:5050"
echo "🛡️ Защита WakeLock: АКТИВИРОВАНА (CPU не спит)."
echo "🦊 Постоянный статус в шторке: ВКЛЮЧЁН."
echo ""
echo "ВАЖНО ДЛЯ REALME UI 5.0 (Сделайте 1 раз):"
echo " 1. Откройте диспетчер недавних задач (смахните вверх)."
echo " 2. Нажмите на 3 точки над карточкой Termux и выберите '🔒 Заблокировать'."
echo " 3. В 'Настройки' -> 'Приложения' -> 'Termux' -> 'Расход батареи' -> выберите 'Без ограничений'."
echo ""
echo "Теперь вы можете полностью выключить компьютер!"
echo "TeleFox будет жить на вашем телефоне и присылать уведомления!"
echo ""
