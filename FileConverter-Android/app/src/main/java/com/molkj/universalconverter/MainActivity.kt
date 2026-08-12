package com.molkj.universalconverter

import android.Manifest
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

/**
 * 万能格式转换器 - 手机版
 *
 * WebView 壳：
 *  - 加载本地 H5 界面（assets/index.html），图片转换在浏览器内完成（canvas）
 *  - 通过 JS 接口把转换结果保存到系统相册
 *  - 支持多选图片（系统文件选择器）
 */
class MainActivity : AppCompatActivity() {

    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    private var isSaving = false
    private var webView: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val webView = WebView(this)
        this.webView = webView
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            loadWithOverviewMode = true
            useWideViewPort = true
        }
        // 禁止跳转外部浏览器（保持在本 WebView）
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                return false
            }
        }
        // 文件选择：支持多选图片
        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.filePathCallback?.onReceiveValue(null)
                this@MainActivity.filePathCallback = filePathCallback
                val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                    type = "image/*"
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    addCategory(Intent.CATEGORY_OPENABLE)
                }
                startActivityForResult(
                    Intent.createChooser(intent, "选择图片（可多选）"),
                    REQ_PICK_IMAGE
                )
                return true
            }
        }
        // JS 桥：保存图片到相册
        webView.addJavascriptInterface(ImageSaver(), "AndroidSaver")

        webView.loadUrl("file:///android_asset/index.html")
        setContentView(webView)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ_PICK_IMAGE) {
            val callback = filePathCallback ?: return
            filePathCallback = null
            if (resultCode != RESULT_OK || data == null) {
                callback.onReceiveValue(null)
                return
            }
            val uris = data.clipData?.let { clip ->
                Array(clip.itemCount) { i -> clip.getItemAt(i).uri }
            } ?: arrayOf(data.data ?: Uri.EMPTY)
            callback.onReceiveValue(uris)
        }
    }

    // 返回键：WebView 可后退时优先后退
    override fun onBackPressed() {
        val wv = webView
        if (wv != null && wv.canGoBack()) {
            wv.goBack()
        } else {
            super.onBackPressed()
        }
    }

    inner class ImageSaver {

        /**
         * 保存 base64 图片到系统相册（Android 10+ 走 MediaStore；9- 需要存储权限）
         * @param base64 图片 base64（不含 data: 前缀）
         * @param fileName 如 photo_1.jpg
         * @param mime 如 image/jpeg
         */
        @JavascriptInterface
        fun saveImage(base64: String, fileName: String, mime: String) {
            runOnUiThread {
                if (isSaving) {
                    toast("正在保存上一张，请稍候…")
                    return@runOnUiThread
                }
                if (Build.VERSION.SDK_INT < 29 &&
                    ContextCompat.checkSelfPermission(
                        this@MainActivity, Manifest.permission.WRITE_EXTERNAL_STORAGE
                    ) != PackageManager.PERMISSION_GRANTED
                ) {
                    ActivityCompat.requestPermissions(
                        this@MainActivity,
                        arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE),
                        REQ_STORAGE
                    )
                    // 授权后需要重试，这里提示用户再次点击
                    toast("请在系统弹窗中允许存储权限，然后再次点击保存")
                    return@runOnUiThread
                }
                doSave(base64, fileName, mime)
            }
        }

        private fun doSave(base64: String, fileName: String, mime: String) {
            isSaving = true
            try {
                val bytes = Base64.decode(base64, Base64.DEFAULT)
                val collection = if (Build.VERSION.SDK_INT >= 29) {
                    MediaStore.Images.Media.getContentUri(
                        MediaStore.VOLUME_EXTERNAL_PRIMARY
                    )
                } else {
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI
                }
                val values = ContentValues().apply {
                    put(MediaStore.Images.Media.DISPLAY_NAME, fileName)
                    put(MediaStore.Images.Media.MIME_TYPE, mime)
                    if (Build.VERSION.SDK_INT >= 29) {
                        put(
                            MediaStore.Images.Media.RELATIVE_PATH,
                            "Pictures/万能格式转换器"
                        )
                    } else {
                        put(MediaStore.Images.Media.DATA, getLegacyPath(fileName))
                    }
                }
                val uri = contentResolver.insert(collection, values)
                    ?: throw IllegalStateException("无法创建图片条目")
                contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                    ?: throw IllegalStateException("无法写入图片")
                toast("已保存：$fileName → 相册/万能格式转换器")
            } catch (e: Exception) {
                toast("保存失败：${e.message}")
            } finally {
                isSaving = false
            }
        }

        @Suppress("DEPRECATION")
        private fun getLegacyPath(fileName: String): String {
            val dir = android.os.Environment.getExternalStoragePublicDirectory(
                android.os.Environment.DIRECTORY_PICTURES
            )
            val folder = java.io.File(dir, "万能格式转换器")
            folder.mkdirs()
            return java.io.File(folder, fileName).absolutePath
        }
    }

    private fun toast(msg: String) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    companion object {
        private const val REQ_PICK_IMAGE = 1001
        private const val REQ_STORAGE = 1002
    }
}
