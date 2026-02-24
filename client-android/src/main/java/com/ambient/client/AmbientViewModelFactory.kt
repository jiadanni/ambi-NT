package com.ambient.client

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.ambient.client.data.SettingsRepository
import com.ambient.client.ui.AmbientViewModel

/**
 * Factory for creating AmbientViewModel with dependencies.
 */
class AmbientViewModelFactory(
    private val settingsRepository: SettingsRepository
) : ViewModelProvider.Factory {
    
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(AmbientViewModel::class.java)) {
            return AmbientViewModel(settingsRepository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
