# 万能格式转换器 · Android 版打包指南

这是一个完整的 **Android Studio 项目**（Kotlin + WebView 壳 + 手机端 H5 界面）。
当前环境无法直接构建 APK（缺 JDK / Android SDK），请在有 **Android Studio** 的电脑上按下面步骤打包。

## 功能说明

| 功能 | 支持 |
|---|---|
| 图片批量转换 | PNG / JPG / WebP 互转（浏览器 canvas 完成，纯本地） |
| 多选图片 | 支持一次选多张（最多 30 张） |
| 尺寸缩放 / 质量调节 | 75% / 50% 缩放，JPEG/WebP 质量滑块 |
| 保存位置 | 自动存入系统「相册 / 万能格式转换器」文件夹 |

> 说明：音视频 / PDF / 压缩包转换依赖桌面端 Python 引擎，手机端 WebView 无法运行，
> 本版聚焦最常用的**图片格式转换**，全部在手机上本地完成、不上传。

## 环境要求

- **Android Studio**（推荐 Koala 2024.1.1 或更新）
- JDK 17（Android Studio 自带）
- Android SDK Platform 34（Android Studio 首次打开时自动下载）

## 打包步骤

1. **下载/拷贝本项目** `FileConverter-Android/` 目录到目标电脑
2. 用 **Android Studio** 打开：`File → Open → 选择 FileConverter-Android 文件夹`
3. 首次打开会提示下载 Gradle 与依赖，点 **Sync Now**，等待完成（需联网，约 5-15 分钟）
4. 连接 Android 手机（开启开发者选项 + USB 调试）可直接运行：
   - 点工具栏 **Run ▶**（绿色三角形）→ 选择你的设备
5. 打包 APK 安装包：
   - 菜单 **Build → Build Bundle(s) / APK(s) → Build APK(s)**
   - 构建完成弹出通知，点 **locate** 打开产物目录：
     `app/build/outputs/apk/debug/app-debug.apk`（调试版）
   - 或生成正式版：菜单 **Build → Generate Signed Bundle / APK…**，按向导创建签名后生成 `app-release.apk`

6. 把 APK 拷贝到手机（微信/数据线均可），点击安装（需允许"安装未知来源应用"）

## 项目结构

```
FileConverter-Android/
├── settings.gradle.kts / build.gradle.kts / gradle.properties
├── gradle/wrapper/gradle-wrapper.properties
└── app/
    ├── build.gradle.kts          # 应用构建配置（minSdk 24 / targetSdk 34）
    └── src/main/
        ├── AndroidManifest.xml   # 清单（含存储权限）
        ├── java/com/molkj/universalconverter/
        │   └── MainActivity.kt   # WebView 壳：加载 H5 + 文件多选 + 相册保存
        ├── res/                  # 图标（多尺寸）、主题、字符串
        └── assets/index.html     # 手机端 H5 界面（图片批量转换，单文件）
```

## 常见问题

**Q: Sync 失败 / 下载慢？**
A: 国内网络可给 Gradle 配置镜像。在 `settings.gradle.kts` 的仓库里加阿里云镜像：
```kotlin
repositories {
    google()
    maven { url = uri("https://maven.aliyun.com/repository/google") }
    maven { url = uri("https://maven.aliyun.com/repository/public") }
    mavenCentral()
}
```

**Q: 图片转 JPG 时透明背景？**
A: 转 JPG 会自动补白底（浏览器 canvas 行为），转 PNG/WebP 保留透明。

**Q: 安卓 7/8/9 保存失败？**
A: 首次保存会请求存储权限，允许后即可；若仍失败请检查系统设置里的存储权限是否开启。

**Q: 每次最多转多少张？**
A: 单次最多 30 张（避免大图内存溢出）。超大图（>8000px）建议先压缩。

## 版本

- 版本号：1.16.0（与桌面版一致）
- 包名：`com.molkj.universalconverter`
