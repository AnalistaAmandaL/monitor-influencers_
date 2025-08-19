#!/usr/bin/env bash

echo "--- Instalando o Google Chrome e dependências ---"

# Atualiza a lista de pacotes
sudo apt-get update

# Instala dependências e utilitários
sudo apt-get install -y wget gnupg

# Baixa e adiciona a chave GPG do repositório do Google
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -

# Adiciona o repositório do Chrome às fontes de software
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list

# Atualiza a lista de pacotes novamente para incluir o novo repositório
sudo apt-get update

# Instala o Google Chrome
sudo apt-get install -y google-chrome-stable

# Corrige permissões e outras dependências
sudo chmod +x /usr/bin/google-chrome

echo "--- Google Chrome instalado com sucesso ---"