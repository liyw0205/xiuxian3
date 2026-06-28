// Pure data-driven text-game framework.
// Runtime scope: render bundle data, evaluate conditions, execute whitelisted actions.

class PureTextGame {
    constructor(bundle) {
        this.bundle = bundle;
        this.version = bundle.schemaVersion || 'pure-text-game@1.0.0';
        this.game = bundle.game || {};
        this.audio = bundle.audio || {};
        this.tracks = this.audio.tracks || {};
        this.scenes = bundle.scenes || {};
        this.initialState = bundle.initialState || {};
        this.state = {};
        this.currentSceneId = this.game.startScene;
        this.history = [];
        this.visited = new Set();
        this.choiceLocked = false;
        this.gotoDepth = 0;
        this.maxGotoDepth = 32;
        this.settings = {
            textSpeed: 50,
            soundEffects: true,
            theme: this.game.defaultTheme || 'default'
        };
        this.typewriterTimer = null;
        this.isTyping = false;
        this.currentText = '';
        this.started = false;
        this.audioManager = new AudioManager();
        this.dom = this.collectDom();
    }

    init() {
        this.validateBundle();
        this.state = this.clone(this.initialState);
        this.audioManager.init(this.settings.soundEffects, 0.5);
        this.applyStaticUi();
        this.setupThemeOptions();
        this.bindEvents();
        this.applyTheme(this.settings.theme);
        this.showWelcome();
    }

    collectDom() {
        return {
            title: document.getElementById('game-title'),
            time: document.getElementById('time-display'),
            chapter: document.getElementById('chapter-display'),
            storyContainer: document.getElementById('story-container'),
            storyText: document.getElementById('story-text'),
            choices: document.getElementById('choices-container'),
            progress: document.getElementById('progress-fill'),
            welcome: document.getElementById('welcome-screen'),
            welcomeTitle: document.getElementById('welcome-title'),
            welcomeSubtitle: document.getElementById('welcome-subtitle'),
            welcomeDescription: document.getElementById('welcome-description'),
            startButton: document.getElementById('start-game-btn'),
            settingsButton: document.getElementById('settings-btn'),
            creditsButton: document.getElementById('credits-btn'),
            settingsModal: document.getElementById('settings-modal'),
            creditsModal: document.getElementById('credits-modal'),
            textSpeed: document.getElementById('text-speed'),
            soundEffects: document.getElementById('sound-effects'),
            themeSelector: document.getElementById('theme-selector')
        };
    }

    applyStaticUi() {
        const ui = this.bundle.ui || {};
        const title = this.game.title || '文游模板';
        const subtitle = this.game.subtitle || '纯 data 驱动的前端文游';

        document.title = title;
        this.dom.title.textContent = title;
        this.dom.welcomeTitle.textContent = title;
        this.dom.welcomeSubtitle.textContent = subtitle;
        this.dom.startButton.textContent = ui.startButton || '开始游戏';
        this.dom.settingsButton.textContent = ui.settingsButton || '设置';
        if (this.dom.creditsButton) {
            this.dom.creditsButton.textContent = ui.creditsButton || '署名';
        }
        this.renderWelcomeDescription(ui.welcome);
    }

    renderWelcomeDescription(lines) {
        this.dom.welcomeDescription.innerHTML = '';
        const description = Array.isArray(lines) && lines.length
            ? lines
            : ['这是一个纯前端、纯 data 驱动的互动文字游戏。', '前端框架只解释数据，不绑定具体业务。'];

        description.forEach(line => {
            const paragraph = document.createElement('p');
            paragraph.textContent = line;
            this.dom.welcomeDescription.appendChild(paragraph);
        });
    }

    setupThemeOptions() {
        const themes = this.bundle.themes || [
            { id: 'default', label: '默认蓝紫' },
            { id: 'warm', label: '暖色橙红' },
            { id: 'cool', label: '冷色青蓝' },
            { id: 'nature', label: '自然绿色' },
            { id: 'dark', label: '深色模式' },
            { id: 'elegant', label: '优雅粉紫' },
            { id: 'rainbow', label: '多彩彩虹' }
        ];

        this.dom.themeSelector.innerHTML = '';
        themes.forEach(theme => {
            const option = document.createElement('option');
            option.value = theme.id;
            option.textContent = theme.label || theme.id;
            this.dom.themeSelector.appendChild(option);
        });
        this.dom.themeSelector.value = this.settings.theme;
    }

    bindEvents() {
        this.dom.startButton.addEventListener('click', () => this.start());
        this.dom.settingsButton.addEventListener('click', () => this.openModal(this.dom.settingsModal));
        if (this.dom.creditsButton && this.dom.creditsModal) {
            this.dom.creditsButton.addEventListener('click', () => this.openModal(this.dom.creditsModal));
        }

        document.querySelectorAll('.close').forEach(button => {
            button.addEventListener('click', () => this.closeAllModals());
        });

        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', event => {
                if (event.target === modal) this.closeAllModals();
            });
        });

        this.dom.textSpeed.addEventListener('input', event => {
            this.settings.textSpeed = Number(event.target.value);
        });

        this.dom.soundEffects.addEventListener('change', event => {
            this.settings.soundEffects = event.target.checked;
            this.audioManager.setEnabled(this.settings.soundEffects);
            if (this.settings.soundEffects && this.currentSceneId) {
                this.runActions(this.getScene(this.currentSceneId).onEnter || []);
            }
        });

        this.dom.themeSelector.addEventListener('change', event => {
            this.settings.theme = event.target.value;
            this.applyTheme(this.settings.theme);
        });

        document.addEventListener('keydown', event => this.handleKeydown(event));
    }

    handleKeydown(event) {
        if (event.key === 'Escape') {
            this.closeAllModals();
            return;
        }

        if (!this.started || this.isModalOpen() || this.isShortcutTarget(event.target)) return;

        if (event.key === ' ') {
            event.preventDefault();
            this.skipText();
            return;
        }

        if (/^[1-9]$/.test(event.key)) {
            const index = Number(event.key) - 1;
            const button = this.dom.choices.querySelectorAll('.choice-btn')[index];
            if (button) button.click();
        }
    }

    isModalOpen() {
        return Array.from(document.querySelectorAll('.modal')).some(modal => modal.getAttribute('aria-hidden') === 'false');
    }

    isShortcutTarget(target) {
        if (!target || !target.closest) return false;
        return !!target.closest('input, textarea, select, button, [contenteditable="true"]');
    }

    showWelcome() {
        this.dom.welcome.classList.remove('hidden');
    }

    start() {
        this.started = true;
        this.dom.welcome.classList.add('hidden');
        setTimeout(() => {
            this.dom.welcome.style.display = 'none';
        }, 300);
        this.resetProgressState();
        this.goto(this.game.startScene);
    }

    goto(sceneId) {
        this.gotoDepth += 1;
        if (this.gotoDepth > this.maxGotoDepth) {
            throw new Error(`Goto depth exceeded limit: ${this.maxGotoDepth}`);
        }

        try {
            const scene = this.getScene(sceneId);
            this.currentSceneId = sceneId;
            this.history.push(sceneId);
            this.visited.add(sceneId);
            this.resetSceneChrome();
            this.updateHeader(scene);
            this.runActions(scene.onEnter || []);
            if (this.currentSceneId !== sceneId) return;
            this.renderBlocks(scene.blocks || []);
            this.renderChoices(scene.choices || []);
            this.updateProgress();
            if (scene.isEnding) this.applyEndingStyle();
        } finally {
            this.gotoDepth -= 1;
        }
    }

    getScene(sceneId) {
        const scene = this.scenes[sceneId];
        if (!scene) {
            throw new Error(`Scene not found: ${sceneId}`);
        }
        return scene;
    }

    updateHeader(scene) {
        this.dom.chapter.textContent = scene.chapter || '';
        this.dom.time.textContent = scene.time || '';
    }

    renderBlocks(blocks) {
        this.clearTypewriter();
        const text = blocks.map(block => this.blockToText(block)).filter(Boolean).join('\n\n');
        this.currentText = text;
        this.dom.storyText.innerHTML = '';

        if (this.settings.textSpeed >= 100) {
            this.dom.storyText.textContent = text;
            return;
        }

        this.isTyping = true;
        let index = 0;
        const speed = Math.max(1, 101 - this.settings.textSpeed);

        const tick = () => {
            if (!this.isTyping || index >= text.length) {
                this.isTyping = false;
                this.typewriterTimer = null;
                return;
            }
            this.dom.storyText.textContent += text.charAt(index);
            index += 1;
            this.typewriterTimer = setTimeout(tick, speed);
        };

        tick();
    }

    blockToText(block) {
        if (!block) return '';
        if (block.type === 'dialogue') {
            const speaker = block.speaker ? `${block.speaker}: ` : '';
            return `${speaker}${block.content || ''}`;
        }
        if (block.type === 'choice-summary') {
            return block.content || '';
        }
        return block.content || block.text || '';
    }

    renderChoices(choices) {
        this.dom.choices.innerHTML = '';
        choices
            .filter(choice => this.evaluateCondition(choice.visibleWhen, true))
            .forEach((choice, index) => {
                const button = document.createElement('button');
                button.className = 'choice-btn';
                button.type = 'button';
                button.textContent = choice.text || `选项 ${index + 1}`;
                button.disabled = this.evaluateCondition(choice.disabledWhen, false);
                button.style.animationDelay = `${index * 0.08}s`;
                button.addEventListener('click', () => this.choose(choice));
                this.dom.choices.appendChild(button);
            });
    }

    choose(choice) {
        if (this.choiceLocked) return;
        if (!this.evaluateCondition(choice.visibleWhen, true) || this.evaluateCondition(choice.disabledWhen, false)) {
            return;
        }

        this.choiceLocked = true;
        this.dom.choices.querySelectorAll('.choice-btn').forEach(button => {
            button.disabled = true;
            button.classList.add('fade-out');
        });

        const delay = this.settings.soundEffects ? 180 : 120;
        const sceneBeforeAction = this.currentSceneId;
        setTimeout(() => {
            let shouldRenderCurrentChoices = false;
            try {
                this.runActions(choice.actions || []);
                shouldRenderCurrentChoices = this.currentSceneId === sceneBeforeAction;
            } finally {
                this.choiceLocked = false;
                if (shouldRenderCurrentChoices) {
                    this.renderChoices(this.getScene(this.currentSceneId).choices || []);
                }
            }
        }, delay);
    }

    runActions(actions) {
        actions.forEach(action => this.runAction(action));
    }

    runAction(action) {
        if (!action || !action.type) {
            throw new Error('Action must include type');
        }

        const handlers = {
            goto: () => this.goto(action.target),
            'state.set': () => this.setByPath(this.state, action.path, action.value),
            'state.add': () => this.setByPath(this.state, action.path, this.getByPath(this.state, action.path, 0) + Number(action.value || 0)),
            'state.toggle': () => this.setByPath(this.state, action.path, !this.getByPath(this.state, action.path, false)),
            'state.push': () => this.pushByPath(this.state, action.path, action.value),
            'state.remove': () => this.removeByPath(this.state, action.path, action.value),
            'flag.set': () => this.setByPath(this.state.flags || (this.state.flags = {}), action.path, action.value),
            'item.add': () => this.addItem(action.id, action.count || 1),
            'item.remove': () => this.removeItem(action.id, action.count || 1),
            'bgm.play': () => this.playBgm(action),
            'bgm.stop': () => this.audioManager.stopAll(),
            notify: () => this.notify(action.message || ''),
            'theme.set': () => this.applyTheme(action.theme || action.value || 'default'),
            ending: () => this.goto(action.target)
        };

        const handler = handlers[action.type];
        if (!handler) {
            throw new Error(`Unknown action type: ${action.type}`);
        }
        handler();
    }

    playBgm(action) {
        if (!this.settings.soundEffects) return;
        const track = this.getBgmTrack(action.id || action.track);
        const src = this.resolveAsset(track.src);
        this.audioManager.play(src, {
            loop: action.loop ?? track.loop ?? true,
            fadeIn: action.fadeIn ?? track.fadeIn ?? true,
            volume: action.volume ?? track.volume ?? this.audio.defaultVolume ?? 0.5,
            forceRestart: !!action.forceRestart
        });
    }

    getBgmTrack(trackId) {
        if (!trackId) {
            throw new Error('bgm.play requires id');
        }
        const track = this.tracks[trackId];
        if (!track) {
            throw new Error(`BGM track not found: ${trackId}`);
        }
        if (!track.src) {
            throw new Error(`BGM track missing src: ${trackId}`);
        }
        return track;
    }

    resolveAsset(src) {
        const base = this.resolveAssetBase(this.game.assetBaseUrl || '');
        if (/^[a-z][a-z0-9+.-]*:/i.test(src) || src.startsWith('//') || src.startsWith('/') || src.includes('..') || src.includes('\\')) {
            throw new Error(`Asset path must be relative to data assets: ${src}`);
        }
        if (!base) return src;
        return `${base.replace(/\/$/, '')}/${src.replace(/^\//, '')}`;
    }

    resolveAssetBase(base) {
        if (!base) return '';
        if (
            base === '/static/yuanqi/audio' ||
            (base.startsWith('/static/yuanqi/audio/') && !base.includes('..') && !base.includes('\\') && !base.includes('//'))
        ) {
            return base;
        }
        if (/^[a-z][a-z0-9+.-]*:/i.test(base) || base.startsWith('//') || base.startsWith('/') || base.includes('\\')) {
            throw new Error(`Asset base must be local, under ../data or /static/yuanqi/audio: ${base}`);
        }
        if (base !== '../data' && !base.startsWith('../data/')) {
            throw new Error(`Asset base must stay under ../data or /static/yuanqi/audio: ${base}`);
        }
        return base;
    }

    evaluateCondition(condition, defaultValue = true) {
        if (condition === undefined || condition === null) return defaultValue;
        if (condition === false) return false;
        if (condition === true) return true;
        if (Array.isArray(condition)) return condition.every(item => this.evaluateCondition(item));
        if (condition.all) return condition.all.every(item => this.evaluateCondition(item));
        if (condition.any) return condition.any.some(item => this.evaluateCondition(item));
        if (condition.not) return !this.evaluateCondition(condition.not);

        const actual = this.getByPath(this.state, condition.path);
        const expected = condition.value;
        switch (condition.op || 'truthy') {
            case '==': return actual === expected;
            case '!=': return actual !== expected;
            case '>': return actual > expected;
            case '>=': return actual >= expected;
            case '<': return actual < expected;
            case '<=': return actual <= expected;
            case 'includes': return Array.isArray(actual) && actual.includes(expected);
            case 'exists': return actual !== undefined && actual !== null;
            case 'truthy': return !!actual;
            case 'falsy': return !actual;
            default: throw new Error(`Unknown condition op: ${condition.op}`);
        }
    }

    updateProgress() {
        const total = Math.max(Object.keys(this.scenes).length, 1);
        const percentage = Math.min((this.visited.size / total) * 100, 100);
        this.dom.progress.style.width = `${percentage}%`;
    }

    resetProgressState() {
        this.history = [];
        this.visited = new Set();
        this.gotoDepth = 0;
        this.choiceLocked = false;
        this.clearTypewriter();
        this.currentText = '';
        this.dom.storyText.textContent = '';
        this.dom.choices.innerHTML = '';
        this.dom.progress.style.width = '0%';
    }

    applyEndingStyle() {
        this.dom.storyContainer.classList.add('ending-scene');
    }

    resetSceneChrome() {
        this.dom.storyContainer.classList.remove('ending-scene');
        this.dom.storyContainer.querySelectorAll('.star').forEach(node => node.remove());
    }

    skipText() {
        if (!this.isTyping) return;
        this.clearTypewriter();
        this.dom.storyText.textContent = this.currentText;
    }

    clearTypewriter() {
        if (this.typewriterTimer) {
            clearTimeout(this.typewriterTimer);
            this.typewriterTimer = null;
        }
        this.isTyping = false;
    }

    addItem(id, count) {
        if (!id) return;
        const inventory = this.state.inventory || (this.state.inventory = {});
        inventory[id] = (inventory[id] || 0) + Number(count || 1);
    }

    removeItem(id, count) {
        if (!id || !this.state.inventory) return;
        const nextCount = (this.state.inventory[id] || 0) - Number(count || 1);
        if (nextCount > 0) this.state.inventory[id] = nextCount;
        else delete this.state.inventory[id];
    }

    notify(message) {
        if (!message) return;
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 1800);
    }

    applyTheme(themeName) {
        const nextTheme = themeName || 'default';
        this.settings.theme = nextTheme;
        document.documentElement.setAttribute('data-theme', nextTheme);
        document.body.setAttribute('data-theme', nextTheme);
        this.dom.themeSelector.value = nextTheme;
    }

    openModal(modal) {
        modal.style.display = 'block';
        modal.setAttribute('aria-hidden', 'false');
    }

    toggleModal(modal) {
        if (modal.style.display === 'block') this.closeAllModals();
        else this.openModal(modal);
    }

    closeAllModals() {
        const activeElement = document.activeElement;
        document.querySelectorAll('.modal').forEach(modal => {
            if (activeElement && modal.contains(activeElement) && activeElement.blur) {
                activeElement.blur();
            }
            modal.style.display = 'none';
            modal.setAttribute('aria-hidden', 'true');
        });
    }

    getByPath(target, path, fallback = undefined) {
        if (!path) return fallback;
        const parts = this.getSafePathParts(path);
        let current = target;
        for (const part of parts) {
            if (current == null || !Object.prototype.hasOwnProperty.call(current, part)) {
                return fallback;
            }
            current = current[part];
        }
        return current;
    }

    setByPath(target, path, value) {
        if (!path) throw new Error('setByPath requires path');
        const parts = this.getSafePathParts(path);
        let current = target;
        parts.slice(0, -1).forEach(part => {
            if (!current[part] || typeof current[part] !== 'object') current[part] = {};
            current = current[part];
        });
        const leaf = parts[parts.length - 1];
        current[leaf] = value;
    }

    pushByPath(target, path, value) {
        const array = this.getByPath(target, path, []);
        if (!Array.isArray(array)) throw new Error(`state.push target is not an array: ${path}`);
        array.push(value);
        this.setByPath(target, path, array);
    }

    removeByPath(target, path, value) {
        const array = this.getByPath(target, path, []);
        if (!Array.isArray(array)) return;
        this.setByPath(target, path, array.filter(item => item !== value));
    }

    assertSafePathSegment(segment) {
        if (!segment || segment === '__proto__' || segment === 'prototype' || segment === 'constructor') {
            throw new Error(`Unsafe state path segment: ${segment}`);
        }
    }

    getSafePathParts(path) {
        if (typeof PureTextGameValidator !== 'undefined') {
            return PureTextGameValidator.safePathParts(path);
        }
        if (typeof path !== 'string' || !path.trim()) {
            throw new Error(`State path must be a non-empty string: ${path}`);
        }
        const parts = path.split('.');
        parts.forEach(part => this.assertSafePathSegment(part));
        return parts;
    }

    clone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    validateBundle() {
        if (typeof PureTextGameValidator === 'undefined') {
            throw new Error('PureTextGameValidator is not loaded');
        }
        PureTextGameValidator.validateBundle(this.bundle);
    }
}

window.PureTextGame = PureTextGame;
