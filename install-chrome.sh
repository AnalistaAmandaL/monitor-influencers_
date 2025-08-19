#!/usr/bin/env bash

echo "--- Instalando o Google Chrome e dependências ---"

sudo apt-get update
sudo apt-get install -y wget gnupg

# Adiciona a chave GPG do repositório do Google
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -

# Adiciona o repositório do Chrome
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list

# Atualiza e instala o Chrome
sudo apt-get update
sudo apt-get install -y google-chrome-stable

echo "--- Google Chrome instalado com sucesso ---"

# ... (seu script de instalação do Chrome) ...

# Adicione esta linha para verificar a versão e imprimi-la no log do Render
google-chrome --version