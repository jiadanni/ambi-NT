package com.ambient.client

import android.app.Application

/**
 * Application class for Ambient Intelligence client.
 * 
 * Minimal setup with no analytics or tracking.
 */
class AmbientApplication : Application() {
    
    override fun onCreate() {
        super.onCreate()
        
        // Explicitly disable debugging features in production
        // No analytics, no crash reporting, no telemetry
    }
    
    override fun onTerminate() {
        super.onTerminate()
        
        // Note: onTerminate() is not guaranteed to be called
        // Crypto keys are cleared in ViewModel.onCleared()
    }
}
