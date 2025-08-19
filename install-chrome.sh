#!/usr/bin/env bash

echo "--- Instalando o Google Chrome e dependências ---"

# Atualiza a lista de pacotes
apt-get update

# Instala utilitários necessários
apt-get install -y wget gnupg

# Baixa e adiciona a chave GPG do repositório do Google
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -

# Adiciona o repositório do Chrome às fontes de software
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list

# Atualiza a lista de pacotes novamente para incluir o novo repositório
apt-get update

# Instala o Google Chrome
apt-get install -y google-chrome-stable

echo "--- Google Chrome instalado com sucesso ---"