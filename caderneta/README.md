# Caderneta Rural — app Android

`www/` é a caderneta (página única) com tudo local: fontes Nunito, jsPDF e o PDF em branco, para funcionar sem internet.
`android/` embrulha a página num WebView; os downloads (cópia de segurança e PDFs) vão para Downloads › Caderneta Rural
pela ponte `CadernetaAndroid`, e as anotações ficam no armazenamento local do aparelho.

O APK é gerado pelo GitHub Actions (`.github/workflows/caderneta-apk.yml`) a cada mudança em `caderneta/` e sai em Releases
com a etiqueta `caderneta-N`.
