#!/usr/bin/env bash

echo "--- Instalando o Google Chrome (Método Direto) ---"

# Atualiza a lista de pacotes
apt-get update

# Instala o wget e o utilitário para descompactar .deb
apt-get install -y wget dpkg

# Baixa o pacote de instalação do Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# Instala o pacote .deb
dpkg -i google-chrome-stable_current_amd64.deb

# Corrige dependências quebradas
apt-get install -f -y

echo "--- Google Chrome instalado com sucesso ---"