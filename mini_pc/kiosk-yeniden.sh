#!/bin/sh
# Paneli yeniden açar: sadece paneli/tarayıcıyı kapatır, kiosk.sh 3 sn sonra
# ~/karavan/tarayici dosyasındaki seçimle (yerel | firefox | ...) yeniden açar.
# kiosk.sh'i KAPATMAYIN: ekran oturumu onunla birlikte kapanır.
pkill -f "karavan/(panel/index.html|yerel_panel/panel.py)" && echo "panel kapatıldı, kiosk yeniden açacak" || echo "çalışan panel yok"
