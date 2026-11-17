# Nextgen Creator

Aplicativo privado para um canal e uma conta. Planeje 20 horas semanais de produção, capture ideias, escreva e aprove roteiros, organize as gravações e envie tarefas com horário ao Google Calendar.

## Rodar localmente

Use Python 3.12, também disponível no Ubuntu 24.04.

```bash
git clone https://github.com/philippy/nextgen-creator.git
cd nextgen-creator
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

O comando `createsuperuser` pede usuário, e-mail e senha. Entre em [127.0.0.1:8000/entrar/](http://127.0.0.1:8000/entrar/) usando o usuário e a senha. Para trocar a senha, rode `.venv/bin/python manage.py changepassword SEU_USUARIO`. Crie uma única conta para esta instalação. O SQLite e as thumbs ficam em `data/` por padrão.

## Configurar o Google Calendar

1. No Google Cloud, habilite a **Google Calendar API**, configure a tela de consentimento e crie um ID OAuth para **Aplicativo da Web**. Adicione a conta que fará a autorização à lista de usuários de teste se o app estiver em modo de teste.
2. Cadastre o URI de redirecionamento da instalação. Use `http://127.0.0.1:8000/configuracoes/google/retorno/` no ambiente local ou `https://creator.seudominio.com/configuracoes/google/retorno/` na VPS. Abra o app pela mesma origem cadastrada.
3. Preencha `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `NEXTGEN_PUBLIC_URL` no `.env`. A última variável recebe só a origem, como `https://creator.seudominio.com`. Reinicie o processo do app.
4. Abra **Configurações**, clique em **Conectar Google Calendar** e conceda as permissões solicitadas. A integração usa `calendar.app.created` para gerir eventos na agenda secundária criada pelo app e `calendar.calendarlist.readonly` para reencontrá-la quando você reconectar. O app identifica sua agenda pela descrição gravada na criação. Mantenha essa descrição para permitir a reconexão à mesma agenda.
5. Salve uma tarefa com horário e abra seus detalhes. Use **Adicionar ao Google Calendar**. Depois, **Abrir no Google Calendar** leva ao evento com o início, o fim e o link da tarefa. Ajustes feitos posteriormente no app ou no Google são independentes. **Desconectar** apaga a credencial salva no app. Para revogar a autorização junto ao Google, use as conexões de terceiros da sua conta.

Em um projeto OAuth externo em modo de teste, o Google pode expirar o token de renovação após sete dias. Se o app avisar que a conexão expirou, autorize de novo em **Configurações**. Para detalhes sobre publicação e permissões, consulte o [OAuth para aplicativos web](https://developers.google.com/identity/protocols/oauth2/web-server) e os [escopos da Calendar API](https://developers.google.com/workspace/calendar/api/auth).

## Implantar na VPS Ubuntu

Prepare um subdomínio com DNS apontado para a VPS, em um bloco HTTPS do servidor web existente. O exemplo usa Nginx, `/opt/nextgen-creator` para o código, `/var/lib/nextgen-creator` para os dados e Gunicorn em `127.0.0.1:8031` com um worker. Se a porta estiver ocupada, ajuste-a no systemd e no proxy.

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv sqlite3
sudo useradd --system --user-group --shell /usr/sbin/nologin nextgen
sudo git clone https://github.com/philippy/nextgen-creator.git /opt/nextgen-creator
cd /opt/nextgen-creator
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
sudo install -d -o nextgen -g nextgen -m 0700 /var/lib/nextgen-creator
sudo install -d -o nextgen -g nextgen -m 0700 /var/lib/nextgen-creator/thumbs
sudo install -o root -g nextgen -m 0640 .env.example .env
sudo .venv/bin/python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
sudoedit .env
```

Use a chave gerada como `DJANGO_SECRET_KEY` e defina estes valores para produção. Substitua o subdomínio de exemplo pelo real. Mantenha o restante do `.env` conforme a configuração OAuth, se for utilizá-la.

```dotenv
DJANGO_DEBUG=0
DJANGO_SECRET_KEY='CHAVE_GERADA'
DJANGO_ALLOWED_HOSTS=creator.seudominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://creator.seudominio.com
NEXTGEN_DATA_DIR=/var/lib/nextgen-creator
NEXTGEN_PUBLIC_URL=https://creator.seudominio.com
```

```bash
sudo -u nextgen .venv/bin/python manage.py migrate
sudo -u nextgen .venv/bin/python manage.py createsuperuser
sudo -u nextgen .venv/bin/python manage.py check --deploy
sudo .venv/bin/python manage.py collectstatic --noinput
sudo install -m 0644 deploy/nextgen-creator.service /etc/systemd/system/nextgen-creator.service
sudo systemctl daemon-reload
sudo systemctl enable --now nextgen-creator
```

Para Nginx, copie `deploy/nginx-locations.conf` para um caminho disponível à configuração e inclua esse arquivo dentro do bloco `server` HTTPS do subdomínio. Se o bloco já define `client_max_body_size`, mantenha uma única diretiva com valor de pelo menos `10m`. Use o certificado TLS existente do subdomínio ou emita-o antes de abrir o app. Mantenha o redirecionamento de HTTP para HTTPS no servidor web. Com outro proxy, replique o encaminhamento de host e protocolo e o limite de upload. Publique somente `staticfiles/` como arquivos estáticos. As thumbs passam pela rota autenticada do Django.

```bash
sudo install -m 0644 deploy/nginx-locations.conf /etc/nginx/nextgen-creator-locations.conf
sudoedit /etc/nginx/sites-available/creator.seudominio.com
# Dentro do bloco HTTPS, inclua: include /etc/nginx/nextgen-creator-locations.conf;
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nextgen-creator
curl -I https://creator.seudominio.com/
```

O HSTS cobre o host do aplicativo. O check do Django pode listar os avisos W005 e W021 para as opções de incluir subdomínios e de habilitar preload, decisões que dependem da política do domínio.

A resposta inicial deve ser um redirecionamento para `/entrar/`. Entre e crie uma tarefa de teste. Para acompanhar o serviço, use `sudo journalctl -u nextgen-creator -n 50`. Antes de atualizar o código, faça backup. Depois da atualização, instale as dependências, rode as migrações, colete os arquivos estáticos e reinicie o serviço. A configuração do Django segue o [checklist de produção do Django 5.2](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## Backup e restauração

Faça o backup com o serviço parado para preservar o mesmo estado no SQLite e nas imagens. O arquivo contém dados privados e a credencial do Google, se conectada. Transfira a cópia para armazenamento protegido fora da VPS. Guarde o `.env` separadamente com as mesmas proteções.

```bash
sudo install -d -m 0700 /var/backups/nextgen-creator
backup="/var/backups/nextgen-creator/nextgen-$(date +%Y%m%d-%H%M%S).tar.gz"
sudo systemctl stop nextgen-creator
sudo bash -c 'umask 077; tar -C /var/lib/nextgen-creator -czf "$1" -- db.sqlite3 thumbs' bash "$backup"
sudo systemctl start nextgen-creator
sudo tar -tzf "$backup"
```

Para restaurar um backup confiável, instale a mesma versão do aplicativo ou uma compatível, mantenha o `.env` configurado e altere o nome do backup no exemplo. Prepare e valide o diretório de restauração antes de parar o site.

```bash
cd /opt/nextgen-creator
backup=/var/backups/nextgen-creator/ARQUIVO.tar.gz
restore="$(sudo mktemp -d /var/lib/nextgen-restore.XXXXXX)"
sudo tar --no-same-owner --no-same-permissions -xzf "$backup" -C "$restore"
sudo sqlite3 "$restore/db.sqlite3" 'PRAGMA integrity_check;'
sudo test -d "$restore/thumbs"
```

Prossiga após o SQLite responder `ok` e o diretório `thumbs` existir. Preserve o diretório anterior até confirmar a restauração.

```bash
previous="/var/lib/nextgen-creator.previous-$(date +%Y%m%d-%H%M%S)"
sudo chown -R nextgen:nextgen "$restore"
sudo chmod 0700 "$restore" "$restore/thumbs"
sudo chmod 0600 "$restore/db.sqlite3"
sudo systemctl stop nextgen-creator
sudo mv /var/lib/nextgen-creator "$previous"
sudo mv "$restore" /var/lib/nextgen-creator
sudo -u nextgen .venv/bin/python manage.py migrate
sudo systemctl start nextgen-creator
```

Entre no app e confira uma tarefa, seu roteiro e a imagem. Se precisar voltar à instalação anterior, pare o serviço, mova a pasta restaurada para outro nome, recoloque `"$previous"` como `/var/lib/nextgen-creator` e inicie o serviço. Para uma restauração local, faça a mesma troca em `data/` com o `runserver` parado.

## Verificar os critérios de aceite

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check
.venv/bin/python manage.py test
```

| Etapa | Como reproduzir |
| --- | --- |
| 1. Tarefas | Crie uma tarefa de 90 minutos para hoje. Em Hoje, conclua e reabra a tarefa. Em Agenda, mova-a para a semana seguinte e confira os totais das duas semanas. |
| 2. Ideias e roteiros | Capture **Entrevista com Vesh** com assunto **Vesh** e uma nota. No mural, converta em **Entrevista**, filtre o rascunho por título, assunto e formato e abra-o pelo post-it. |
| 3. Produção | Aprove o roteiro, defina o título, anexe um JPG ou PNG e agende a gravação para hoje. Abra o roteiro a partir da tarefa em Hoje, conclua a gravação e confira o saldo da semana. Saia e tente abrir a URL da thumb. |
| 4. Calendar e VPS | Os testes simulam a perda da primeira resposta do Google e verificam que a tentativa seguinte recupera um único evento. Na conta real, conecte a agenda e confirme início, fim, fuso e link. Restaure um backup de teste e abra a tarefa e a imagem recuperadas. |

O fundo fotográfico de Hoje é um asset do projeto inspirado nas referências visuais. A fonte Instrument Sans é servida localmente sob a licença SIL Open Font License, incluída junto ao arquivo.
