// 智能音频管理器
class AudioManager {
    constructor() {
        // 存储音频实例
        this.audioInstances = new Map();
        // 当前播放的音频路径
        this.currentAudioPath = null;
        // 音效开关状态
        this.enabled = true;
        // 音量
        this.volume = 0.5;
        // 淡入淡出时长（毫秒）
        this.fadeDuration = 1000;
        this.fadeTimers = new Map();
    }

    // 初始化
    init(enabled = true, volume = 0.5) {
        this.enabled = enabled;
        this.volume = volume;
    }

    // 播放音频
    play(audioPath, options = {}) {
        if (!this.enabled || !audioPath) return;

        const {
            loop = true,
            fadeIn = true,
            volume = this.volume,
            forceRestart = false
        } = options;
        const numericVolume = Number(volume);
        const nextVolume = Number.isFinite(numericVolume)
            ? Math.max(0, Math.min(1, numericVolume))
            : this.volume;
        this.volume = nextVolume;

        // 如果是同一个音频且不强制重启
        if (audioPath === this.currentAudioPath && !forceRestart) {
            const currentAudio = this.audioInstances.get(audioPath);
            if (currentAudio && !currentAudio.paused) {
                this.clearFade(currentAudio);
                currentAudio.loop = loop;
                currentAudio.volume = this.volume;
                // 音频正在播放，不做任何操作
                return;
            } else if (currentAudio && currentAudio.paused) {
                // 音频暂停中，继续播放
                this.resume(audioPath, fadeIn);
                return;
            }
        }

        // 如果是不同的音频，先暂停当前音频
        if (this.currentAudioPath && this.currentAudioPath !== audioPath) {
            this.pause(this.currentAudioPath, true);
        }

        // 获取或创建音频实例
        let audio = this.audioInstances.get(audioPath);
        if (!audio) {
            audio = new Audio(audioPath);
            audio.loop = loop;
            this.audioInstances.set(audioPath, audio);
            
            // 音频加载错误处理
            audio.onerror = () => {
                console.warn(`Failed to load audio: ${audioPath}`);
                this.clearFade(audio);
                this.audioInstances.delete(audioPath);
            };
        }

        // 设置音量和循环
        audio.loop = loop;
        
        // 如果强制重启，从头播放
        if (forceRestart) {
            audio.currentTime = 0;
        }

        // 淡入效果
        if (fadeIn) {
            this.clearFade(audio);
            audio.volume = 0;
            audio.play().catch(e => {
                console.warn('Audio play failed:', e);
            });
            this.fadeIn(audio);
        } else {
            this.clearFade(audio);
            audio.volume = this.volume;
            audio.play().catch(e => {
                console.warn('Audio play failed:', e);
            });
        }

        this.currentAudioPath = audioPath;
    }

    // 暂停音频
    pause(audioPath = null, fadeOut = true) {
        const path = audioPath || this.currentAudioPath;
        if (!path) return;

        const audio = this.audioInstances.get(path);
        if (!audio || audio.paused) return;

        if (fadeOut) {
            this.fadeOut(audio, () => {
                audio.pause();
            });
        } else {
            this.clearFade(audio);
            audio.pause();
        }
    }

    // 继续播放
    resume(audioPath = null, fadeIn = true) {
        const path = audioPath || this.currentAudioPath;
        if (!path) return;

        const audio = this.audioInstances.get(path);
        if (!audio || !audio.paused) return;

        if (fadeIn) {
            this.clearFade(audio);
            audio.volume = 0;
            audio.play().catch(e => {
                console.warn('Audio resume failed:', e);
            });
            this.fadeIn(audio);
        } else {
            this.clearFade(audio);
            audio.volume = this.volume;
            audio.play().catch(e => {
                console.warn('Audio resume failed:', e);
            });
        }

        this.currentAudioPath = path;
    }

    // 停止音频
    stop(audioPath = null) {
        const path = audioPath || this.currentAudioPath;
        if (!path) return;

        const audio = this.audioInstances.get(path);
        if (!audio) return;

        this.clearFade(audio);
        audio.pause();
        audio.currentTime = 0;
        
        if (path === this.currentAudioPath) {
            this.currentAudioPath = null;
        }
    }

    // 停止所有音频
    stopAll() {
        this.audioInstances.forEach((audio, path) => {
            this.clearFade(audio);
            audio.pause();
            audio.currentTime = 0;
        });
        this.currentAudioPath = null;
    }

    // 设置音量
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        this.audioInstances.forEach(audio => {
            if (!audio.paused) {
                this.clearFade(audio);
                audio.volume = this.volume;
            }
        });
    }

    // 设置启用状态
    setEnabled(enabled) {
        this.enabled = enabled;
        if (!enabled) {
            this.pauseAll();
        }
    }

    // 暂停所有音频
    pauseAll() {
        this.audioInstances.forEach((audio, path) => {
            if (!audio.paused) {
                this.pause(path, true);
            }
        });
    }

    // 淡入效果
    fadeIn(audio) {
        this.clearFade(audio);
        const startVolume = 0;
        const endVolume = this.volume;
        const duration = this.fadeDuration;
        const increment = (endVolume - startVolume) / (duration / 10);
        
        audio.volume = startVolume;
        if (endVolume <= 0 || increment <= 0) {
            audio.volume = endVolume;
            return;
        }
        
        const fadeInterval = setInterval(() => {
            if (audio.volume < endVolume - increment) {
                audio.volume += increment;
            } else {
                audio.volume = endVolume;
                clearInterval(fadeInterval);
                this.fadeTimers.delete(audio);
            }
        }, 10);
        this.fadeTimers.set(audio, fadeInterval);
    }

    // 淡出效果
    fadeOut(audio, callback) {
        this.clearFade(audio);
        const startVolume = audio.volume;
        const endVolume = 0;
        const duration = this.fadeDuration;
        const decrement = startVolume / (duration / 10);
        if (startVolume <= 0 || decrement <= 0) {
            audio.volume = endVolume;
            if (callback) callback();
            return;
        }
        
        const fadeInterval = setInterval(() => {
            if (audio.volume > decrement) {
                audio.volume -= decrement;
            } else {
                audio.volume = endVolume;
                clearInterval(fadeInterval);
                this.fadeTimers.delete(audio);
                if (callback) callback();
            }
        }, 10);
        this.fadeTimers.set(audio, fadeInterval);
    }

    clearFade(audio) {
        const fadeInterval = this.fadeTimers.get(audio);
        if (fadeInterval) {
            clearInterval(fadeInterval);
            this.fadeTimers.delete(audio);
        }
    }

    // 预加载音频
    preload(audioPaths) {
        if (!Array.isArray(audioPaths)) {
            audioPaths = [audioPaths];
        }

        audioPaths.forEach(path => {
            if (path && !this.audioInstances.has(path)) {
                const audio = new Audio(path);
                audio.preload = 'auto';
                this.audioInstances.set(path, audio);
            }
        });
    }

    // 获取当前播放状态
    getPlaybackStatus(audioPath = null) {
        const path = audioPath || this.currentAudioPath;
        if (!path) return null;

        const audio = this.audioInstances.get(path);
        if (!audio) return null;

        return {
            path: path,
            playing: !audio.paused,
            currentTime: audio.currentTime,
            duration: audio.duration,
            volume: audio.volume,
            loop: audio.loop
        };
    }

    // 清理未使用的音频实例
    cleanup(keepCurrent = true) {
        this.audioInstances.forEach((audio, path) => {
            if (keepCurrent && path === this.currentAudioPath) {
                return;
            }
            if (audio.paused) {
                this.clearFade(audio);
                audio.src = '';
                this.audioInstances.delete(path);
            }
        });
    }
}

// 导出音频管理器
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AudioManager;
}
