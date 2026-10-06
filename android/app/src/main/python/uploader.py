import logging
import aiohttp

logger = logging.getLogger("uploader")

def _build_form_data(file_bytes: bytes, filename: str, metadata: dict, content_type: str):
    form_data = aiohttp.FormData()
    form_data.add_field(
        name="file",
        value=file_bytes,
        filename=filename,
        content_type=content_type
    )
    for key, value in metadata.items():
        form_data.add_field(name=key, value=str(value if value is not None else ""))
    return form_data

async def send_to_n8n(
    webhook_url: str,
    file_bytes: bytes,
    filename: str,
    metadata: dict,
    content_type: str = "application/octet-stream"
) -> bool:
    """
    Отправляет бинарный файл и метаданные контакта в Webhook n8n через multipart/form-data.
    Автоматически пробует переключиться между Production (/webhook/) и Test (/webhook-test/) URL в случае 404.
    """
    if not webhook_url:
        logger.warning("N8N_WEBHOOK_URL не указан, пропуск отправки.")
        return False

    urls_to_try = [webhook_url]
    if "/webhook/" in webhook_url:
        urls_to_try.append(webhook_url.replace("/webhook/", "/webhook-test/"))
    elif "/webhook-test/" in webhook_url:
        urls_to_try.append(webhook_url.replace("/webhook-test/", "/webhook/"))

    try:
        async with aiohttp.ClientSession() as session:
            for i, target_url in enumerate(urls_to_try):
                form_data = _build_form_data(file_bytes, filename, metadata, content_type)
                logger.info(f"-> Отправка файла '{filename}' ({len(file_bytes)} байт) в n8n: {target_url}")
                
                try:
                    async with session.post(target_url, data=form_data, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status in (200, 201, 204):
                            mode = "Test URL" if "/webhook-test/" in target_url else "Production URL"
                            logger.info(f"[+] Успешно доставлено в n8n ({mode}, HTTP {resp.status})")
                            return True
                        elif resp.status == 404 and i < len(urls_to_try) - 1:
                            logger.warning(f"URL {target_url} вернул 404 (не активен). Пробуем альтернативный эндпоинт...")
                            continue
                        else:
                            text = await resp.text()
                            logger.error(f"[!] Ошибка n8n HTTP {resp.status}: {text[:200]}")
                            if resp.status == 404:
                                logger.warning(
                                    "[ПОДСКАЗКА] В n8n воркфлоу еще не запущен. Либо включите тумблер 'Active' в правом верхнем углу n8n, "
                                    "либо нажмите 'Listen for test event' в ноде Webhook."
                                )
                            return False
                except Exception as e:
                    if i < len(urls_to_try) - 1:
                        continue
                    raise e

    except aiohttp.ClientConnectorError:
        logger.error(f"[!] Не удалось подключиться к n8n по адресу {webhook_url}. Убедитесь, что n8n запущен на http://localhost:5678.")
        return False
    except Exception as e:
        logger.exception(f"[!] Непредвиденная ошибка отправки в n8n: {e}")
        return False
