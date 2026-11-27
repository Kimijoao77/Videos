Teste de acesso para a tarefa do Lince Lunar, sem mudar nada. A pasta atual é uma cópia do Engfy. Rode estes comandos e responda uma linha por item com "ok" ou "falhou" (sem mostrar tokens nem conteúdo de arquivos):
1. `python3 -c "import json;d=json.load(open('canal/lince/dados/evolucao.json'));print(len(d['videos']))"`
2. `GH_TOKEN=$VIDEOS_TOKEN gh api repos/Kimijoao77/Videos/actions/workflows/lince-monta.yml --jq .state`
3. `GH_TOKEN=$VIDEOS_TOKEN gh api repos/Kimijoao77/Videos/actions/workflows/lince-postar.yml --jq .state`
4. `gh release view lince-lunar -R Kimijoao77/Engfy --json tagName --jq .tagName`
5. `git push --dry-run origin HEAD:main`
6. `ffmpeg -version | head -1`
Não faça commit.
