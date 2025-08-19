#!/usr/bin/env bash

echo "--- Instalando o Google Chrome ---"

# Atualiza a lista de pacotes
sudo apt-get update

# Instala o wget para baixar o arquivo .deb
sudo apt-get install -y wget

# Baixa o pacote de instalação do Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# Instala o pacote .deb
sudo dpkg -i google-chrome-stable_current_amd64.deb

# Corrige dependências quebradas
sudo apt-get install -f -y

echo "--- Google Chrome instalado com sucesso ---"

# Define a variável de ambiente (opcional, mas uma boa prática)
echo 'export CHROME_PATH="/usr/bin/google-chrome"' >> ~/.profile