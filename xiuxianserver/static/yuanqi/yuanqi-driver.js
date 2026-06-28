(function () {
    'use strict';

    const form = document.getElementById('yuanqi-form');
    const gate = document.getElementById('yuanqi-gate');
    const nameInput = document.getElementById('yuanqi-name');
    const codeInput = document.getElementById('yuanqi-code');
    const statusText = document.getElementById('yuanqi-status');
    const submitButton = document.getElementById('yuanqi-submit');
    const gameRoot = document.getElementById('game-root');

    if (!form || !gate || !nameInput || !codeInput || !statusText || !submitButton || !gameRoot) {
        return;
    }

    form.addEventListener('submit', event => {
        event.preventDefault();
        startYuanqi().catch(error => {
            setBusy(false);
            setStatus(error && error.message ? error.message : '缘契开启失败。', true);
        });
    });

    async function startYuanqi() {
        const name = nameInput.value.trim();
        const code = codeInput.value.trim();
        if (!name) {
            setStatus('请填写角色名。', true);
            nameInput.focus();
            return;
        }
        if (!code) {
            setStatus('请填写缘契开启码。', true);
            codeInput.focus();
            return;
        }

        setBusy(true);
        setStatus('正在校验缘契开启码...', false);

        const response = await fetch('/xiuxian/yuanqi/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, code })
        });
        const payload = await readJson(response);
        if (!response.ok) {
            throw new Error(errorMessage(payload, response.status));
        }

        const bundle = prepareBundle(payload.story_data, payload.player_name || name);
        window.game = new window.PureTextGame(bundle);
        window.game.init();
        if (window.game && typeof window.game.start === 'function') {
            window.game.start();
        }
        gameRoot.removeAttribute('aria-hidden');
        gate.classList.add('hidden');
        setBusy(false);
    }

    async function readJson(response) {
        try {
            return await response.json();
        } catch (_error) {
            return {};
        }
    }

    function errorMessage(payload, status) {
        if (payload && typeof payload.detail === 'string' && payload.detail.trim()) {
            return payload.detail.trim();
        }
        return `缘契开启失败（${status}）。`;
    }

    function prepareBundle(rawBundle, playerName) {
        if (!rawBundle || typeof rawBundle !== 'object') {
            throw new Error('缘契剧本数据异常。');
        }
        const bundle = clone(rawBundle);
        const name = String(playerName || '').trim();
        bundle.initialState = bundle.initialState && typeof bundle.initialState === 'object'
            ? bundle.initialState
            : {};
        bundle.initialState.player = bundle.initialState.player && typeof bundle.initialState.player === 'object'
            ? bundle.initialState.player
            : {};
        bundle.initialState.player.name = name;
        applyNamePlaceholders(bundle, name);
        return bundle;
    }

    function applyNamePlaceholders(bundle, name) {
        replaceString(bundle.game, 'title', name);
        replaceString(bundle.game, 'subtitle', name);

        if (bundle.ui && typeof bundle.ui === 'object') {
            replaceString(bundle.ui, 'startButton', name);
            replaceString(bundle.ui, 'settingsButton', name);
            replaceString(bundle.ui, 'loadingText', name);
            if (Array.isArray(bundle.ui.welcome)) {
                bundle.ui.welcome = bundle.ui.welcome.map(line => replaceName(line, name));
            }
        }

        if (Array.isArray(bundle.themes)) {
            bundle.themes.forEach(theme => replaceString(theme, 'label', name));
        }

        const scenes = bundle.scenes && typeof bundle.scenes === 'object' ? bundle.scenes : {};
        Object.keys(scenes).forEach(sceneId => {
            const scene = scenes[sceneId];
            if (!scene || typeof scene !== 'object') return;
            replaceString(scene, 'chapter', name);
            replaceString(scene, 'time', name);
            replaceBlocks(scene.blocks, name);
            replaceChoices(scene.choices, name);
            replaceActions(scene.onEnter, name);
        });
    }

    function replaceBlocks(blocks, name) {
        if (!Array.isArray(blocks)) return;
        blocks.forEach(block => {
            if (!block || typeof block !== 'object') return;
            replaceString(block, 'speaker', name);
            replaceString(block, 'content', name);
            replaceString(block, 'text', name);
        });
    }

    function replaceChoices(choices, name) {
        if (!Array.isArray(choices)) return;
        choices.forEach(choice => {
            if (!choice || typeof choice !== 'object') return;
            replaceString(choice, 'text', name);
            replaceActions(choice.actions, name);
        });
    }

    function replaceActions(actions, name) {
        if (!Array.isArray(actions)) return;
        actions.forEach(action => {
            if (!action || typeof action !== 'object') return;
            if (action.type === 'notify') {
                replaceString(action, 'message', name);
            }
        });
    }

    function replaceString(target, key, name) {
        if (!target || typeof target !== 'object' || typeof target[key] !== 'string') {
            return;
        }
        target[key] = replaceName(target[key], name);
    }

    function replaceName(value, name) {
        return typeof value === 'string' ? value.replace(/\{\{name\}\}/g, name) : value;
    }

    function clone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function setBusy(isBusy) {
        submitButton.disabled = isBusy;
        submitButton.textContent = isBusy ? '校验中...' : '进入缘契';
    }

    function setStatus(message, isError) {
        statusText.textContent = message || '';
        statusText.classList.toggle('error', Boolean(isError));
    }
})();
