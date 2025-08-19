#!/bin/sh
mkdir -p ~/.streamlit/
echo "[general]
email = \"\"
" > ~/.streamlit/credentials.toml
echo "[server]
headless = true
enableCORS = false
" > ~/.streamlit/config.toml