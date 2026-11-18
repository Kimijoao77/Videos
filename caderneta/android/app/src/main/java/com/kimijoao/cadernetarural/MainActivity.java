package com.kimijoao.cadernetarural;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Toast;
import androidx.core.content.FileProvider;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/** A Caderneta Rural roda dentro de um WebView, sem internet; as anotações ficam guardadas no próprio aparelho. */
public final class MainActivity extends Activity {
    private static final int ESCOLHER_ARQUIVO = 42;
    private WebView webView;
    private ValueCallback<Uri[]> escolha;

    @Override
    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    public void onCreate(Bundle state) {
        super.onCreate(state);
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(244, 241, 248));
        webView.setFitsSystemWindows(true);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setTextZoom(100);

        WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();
        webView.setWebViewClient(new WebViewClientCompat() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("appassets.androidplatform.net".equals(uri.getHost())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (ActivityNotFoundException ignored) {
                }
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (escolha != null) escolha.onReceiveValue(null);
                escolha = callback;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                try {
                    startActivityForResult(Intent.createChooser(i, "Escolha a cópia da caderneta"), ESCOLHER_ARQUIVO);
                } catch (ActivityNotFoundException e) {
                    escolha = null;
                    return false;
                }
                return true;
            }
        });
        webView.addJavascriptInterface(new Ponte(), "CadernetaAndroid");
        if (state == null || webView.restoreState(state) == null) {
            webView.loadUrl("https://appassets.androidplatform.net/assets/index.html");
        }
    }

    /** Recebe os arquivos que a caderneta quer baixar (cópia .json e PDFs). */
    private final class Ponte {
        @JavascriptInterface
        public String salvar(String nome, String base64, String tipo) {
            try {
                String limpo = nome.replaceAll("[^\\p{L}\\p{N}._ -]", "_");
                byte[] dados = Base64.decode(base64, Base64.DEFAULT);
                File pasta = new File(getCacheDir(), "saida");
                pasta.mkdirs();
                File arq = new File(pasta, limpo);
                try (FileOutputStream out = new FileOutputStream(arq)) {
                    out.write(dados);
                }
                boolean emDownloads = false;
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.MediaColumns.DISPLAY_NAME, limpo);
                    v.put(MediaStore.MediaColumns.MIME_TYPE, tipo);
                    v.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Caderneta Rural");
                    Uri u = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    if (u != null) {
                        try (OutputStream out = getContentResolver().openOutputStream(u)) {
                            if (out != null) { out.write(dados); emDownloads = true; }
                        }
                    }
                }
                final boolean salvo = emDownloads;
                runOnUiThread(() -> abrir(arq, tipo, salvo));
                return "ok";
            } catch (Exception e) {
                return "erro";
            }
        }
    }

    private void abrir(File arq, String tipo, boolean salvo) {
        if (salvo) Toast.makeText(this, "Salvo em Downloads › Caderneta Rural", Toast.LENGTH_LONG).show();
        Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".arquivos", arq);
        Intent i;
        if ("application/pdf".equals(tipo)) {
            i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(uri, tipo);
        } else {
            i = new Intent(Intent.ACTION_SEND);
            i.setType(tipo);
            i.putExtra(Intent.EXTRA_STREAM, uri);
        }
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivity(Intent.createChooser(i, salvo ? "Abrir ou enviar" : "Salvar ou enviar"));
        } catch (ActivityNotFoundException ignored) {
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == ESCOLHER_ARQUIVO && escolha != null) {
            Uri u = resultCode == RESULT_OK && data != null ? data.getData() : null;
            escolha.onReceiveValue(u != null ? new Uri[]{u} : null);
            escolha = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
            return;
        }
        new AlertDialog.Builder(this)
                .setMessage("Fechar a caderneta?")
                .setPositiveButton("Fechar", (dialog, which) -> finish())
                .setNegativeButton("Continuar", null)
                .show();
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        webView.saveState(state);
        super.onSaveInstanceState(state);
    }

    @Override
    protected void onPause() {
        webView.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
    }

    @Override
    protected void onDestroy() {
        webView.destroy();
        super.onDestroy();
    }
}
