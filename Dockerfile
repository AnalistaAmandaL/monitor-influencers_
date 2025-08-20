# Use uma imagem base Python que já tenha as dependências do Playwright
FROM mcr.microsoft.com/playwright:v1.39.0-jammy

# Instalar o Poetry
RUN pip install poetry

# Definir o diretório de trabalho no contêiner
WORKDIR /app

# Copiar os arquivos de gerenciamento de dependência
# Copiar apenas esses arquivos primeiro permite que o Docker use o cache de camadas
COPY pyproject.toml poetry.lock ./

# Instalar as dependências do projeto usando o Poetry
# O --no-root evita a instalação do pacote atual
RUN poetry install --no-root

# Copiar o restante do código da sua aplicação
COPY . .

# Expor a porta que o Streamlit usa (geralmente 8501)
EXPOSE 8501

# Comando para iniciar a aplicação Streamlit
CMD ["poetry", "run", "streamlit", "run", "app.py"]