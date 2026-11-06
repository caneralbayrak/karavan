#!/bin/sh
# Karavan paneli: tarayıcı tam ekran (kiosk). Kapanır/çökerse 3 sn sonra yeniden açılır.
# DİKKAT: Bu betik ekran oturumunun ana programıdır; kapanırsa ekran oturumu da kapanır.
# Tarayıcıyı değiştirmek/yeniden açmak için sadece tarayıcıyı kapatın (kiosk-yeniden.sh).
ADRES="file://$HOME/karavan/panel/index.html?broker=localhost"
# Dokunmatik kalibrasyonu (2026-10-31, kalibrasyon.html ile ölçüldü)
xinput set-prop "DIALOGUE INC PenMount USB" "libinput Calibration Matrix" 1.03393 0 -0.02019 0 1.07413 -0.03203 0 0 1 2>/dev/null
# L/R ön tuşları (dahili PS/2 fare, i8042.nomux=1 ile görünür) tıklama yapmasın: sol(1)->8, sağ(3)->9
# Panel isterse <Button-8> / <Button-9> olarak yakalayabilir. (2026-11-06)
xinput set-button-map "PS/2 Generic Mouse" 8 2 9 2>/dev/null
# Dokunmatik ekranda fare imleci görünmesin
command -v unclutter >/dev/null && unclutter -idle 3 -root &
while true; do
  # Seçim her açılışta okunur: yerel | firefox | chromium | surf
  TARAYICI=$(cat "$HOME/karavan/tarayici" 2>/dev/null || echo firefox)
  case "$TARAYICI" in
    yerel)
      # Tarayıcısız yerel panel (Python/Tk): bu işlemcide anında tepki verir
      python3 "$HOME/karavan/yerel_panel/panel.py" 2>>"$HOME/.karavan-panel.log" ;;
    chromium)
      chromium --kiosk --no-first-run --noerrdialogs --disable-infobars \
        --autoplay-policy=no-user-gesture-required --password-store=basic \
        --disable-translate --disable-features=Translate,MediaRouter \
        --disable-background-networking --disable-component-update --disable-sync \
        --renderer-process-limit=1 --disable-pinch --overscroll-history-navigation=0 \
        --user-data-dir="$HOME/.karavan-chromium" "$ADRES" ;;
    surf)
      surf -F "$ADRES" ;;
    *)
      firefox-esr --kiosk --no-remote --profile "$HOME/.karavan-kiosk" "$ADRES" ;;
  esac
  sleep 3
done
