# Videos

Fábrica dos canais **Aqui Há Dragões** (português) e **Here Be Dragons** (inglês): documentários ilustrados sobre
a era dos galeões (1500 a 1750), com mistérios, naufrágios e piratas.

Tudo é feito por código:

- **Cenas:** desenhadas em Python (Pillow), no estilo de ilustração chapada: mar em corte, galeões, mapas antigos,
  calendários, pedras entalhadas. Nenhuma imagem é gerada por IA.
- **Voz:** a do dono do canal, clonada com o [Chatterbox Multilingual](https://github.com/resemble-ai/chatterbox)
  (código aberto, roda só no processador).
- **Trilha, efeitos, miniatura e montagem:** por código, com ffmpeg.

## Como funciona

1. O roteiro (falas em português e inglês, a cena de cada fala, as etiquetas e as fontes conferidas) fica no
   repositório privado do canal.
2. O fluxo [Fábrica](.github/workflows/fabrica.yml) acha o roteiro novo, narra cada fala, desenha as cenas, monta
   o vídeo de cada idioma e devolve tudo para o repositório privado, onde o dono assiste e aprova antes de postar.
3. O fluxo [Espelho do código](.github/workflows/espelho.yml) copia o código da fábrica para [`codigo/`](codigo)
   todo dia.

Os roteiros, a gravação da voz e os vídeos nunca ficam aqui: o fluxo não publica arquivos e o registro dele não
mostra o texto das falas.
