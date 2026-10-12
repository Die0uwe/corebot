#!/bin/bash
# Testomgeving voor de site: kopie van site/, schone database "corebot", nep-Discord (poort 8097) en PHP-server (poort 8098).
# Vereist: php 8 met pdo_mysql en curl, MariaDB (draaiend, root via socket), python3 met requests en playwright (chromium).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"; RUN=/tmp/corebot-run
fuser -k 8097/tcp 8098/tcp >/dev/null 2>&1 || true
rm -rf "$RUN" && mkdir -p "$RUN" && cp -r "$HERE/../site/." "$RUN/"
mariadb -uroot -e "drop database if exists corebot; create database corebot character set utf8mb4; create user if not exists cb@127.0.0.1 identified by 'cbpass'; create user if not exists cb@localhost identified by 'cbpass'; grant all on corebot.* to cb@127.0.0.1; grant all on corebot.* to cb@localhost;"
cat > "$RUN/config.php" <<'PHP'
<?php
return ['db_host'=>'127.0.0.1','db_port'=>3306,'db_name'=>'corebot','db_user'=>'cb','db_pass'=>'cbpass','app_key'=>'base64:'.base64_encode(str_repeat('k',32)),
 'hub_secret'=>'testhubsecret-0123456789abcdef0123456789abcdef','discord_client_id'=>'123456789012345678','discord_client_secret'=>'geheim-geheim-geheim',
 'admin_discord_ids'=>['999999999999999999'],'contact_email'=>'privacy@corebot.info','allowed_hosts'=>['127.0.0.1:8098','corebot.scriptspace.nl','corebot.info'],'debug'=>true];
PHP
echo '<?php define("CB_TEST_DISCORD","http://127.0.0.1:8097");' > /tmp/cb_prepend.php
(nohup python3 "$HERE/fake_discord.py" >/dev/null 2>&1 &)
(cd "$RUN" && nohup php -d auto_prepend_file=/tmp/cb_prepend.php -S 127.0.0.1:8098 >/tmp/cb_php.log 2>&1 &)
sleep 1.5; curl -s http://127.0.0.1:8098/health.php; echo
