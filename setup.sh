mkdir -p ~/.streamlit/

echo "\
[server]\n\
headless = true\n\
port = $PORT\n\
enableCORS = false\n\
\n\
[theme]\n\
primaryColor = '#013369'\n\
backgroundColor = '#ffffff'\n\
secondaryBackgroundColor = '#f0f2f6'\n\
textColor = '#31333f'\n\
font = 'sans serif'\n\
" > ~/.streamlit/config.toml

# Comando de seguridad para asegurar que spacy tenga el modelo
python -m spacy download es_core_news_sm