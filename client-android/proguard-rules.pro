# Ambient Intelligence - Privacy-First ProGuard Configuration

# Keep crypto classes (JNA uses reflection)
-keep class com.goterl.** { *; }
-keep class com.sun.jna.** { *; }
-dontwarn com.sun.jna.**

# Keep serialization classes
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Keep data models for serialization
-keep,includedescriptorclasses class com.ambient.client.network.**$$serializer { *; }
-keepclassmembers class com.ambient.client.network.** {
    *** Companion;
}
-keepclasseswithmembers class com.ambient.client.network.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-keepnames class okhttp3.internal.publicsuffix.PublicSuffixDatabase

# Remove all logging in release builds for privacy
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
    public static *** i(...);
    public static *** w(...);
    public static *** e(...);
}

# Optimize aggressively
-optimizationpasses 5
-allowaccessmodification
-dontpreverify
