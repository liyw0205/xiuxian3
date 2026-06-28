(function (root, factory) {
    const api = factory();
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    if (root) {
        root.PureTextGameValidator = api;
    }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    const BUILTIN_THEME_IDS = new Set(['default', 'warm', 'cool', 'nature', 'dark', 'elegant', 'rainbow']);
    const ACTION_TYPES = new Set([
        'goto',
        'ending',
        'state.set',
        'state.add',
        'state.toggle',
        'state.push',
        'state.remove',
        'flag.set',
        'item.add',
        'item.remove',
        'bgm.play',
        'bgm.stop',
        'notify',
        'theme.set'
    ]);
    const TRANSITION_TYPES = new Set(['goto', 'ending']);
    const CONDITION_OPS = new Set(['==', '!=', '>', '>=', '<', '<=', 'includes', 'exists', 'truthy', 'falsy']);
    const BLOCK_TYPES = new Set(['text', 'dialogue', 'choice-summary']);
    const PROHIBITED_PATH_SEGMENTS = new Set(['__proto__', 'prototype', 'constructor']);

    function assert(condition, message) {
        if (!condition) {
            throw new Error(message);
        }
    }

    function isPlainObject(value) {
        return !!value && typeof value === 'object' && !Array.isArray(value);
    }

    function assertPlainObject(value, label) {
        assert(isPlainObject(value), `${label} must be an object`);
    }

    function assertString(value, label) {
        assert(typeof value === 'string' && value.trim(), `${label} must be a non-empty string`);
    }

    function assertBoolean(value, label) {
        assert(typeof value === 'boolean', `${label} must be a boolean`);
    }

    function assertNumber(value, label) {
        assert(typeof value === 'number' && Number.isFinite(value), `${label} must be a finite number`);
    }

    function assertRange(value, min, max, label) {
        assertNumber(value, label);
        assert(value >= min && value <= max, `${label} must be between ${min} and ${max}`);
    }

    function safePathParts(path) {
        assertString(path, `State path: ${path}`);
        const parts = path.split('.');
        assert(parts.every(part => part.length > 0), `State path must not contain empty segments: ${path}`);
        parts.forEach(part => {
            if (PROHIBITED_PATH_SEGMENTS.has(part)) {
                throw new Error(`Unsafe state path segment: ${part}`);
            }
        });
        return parts;
    }

    function resolveAssetBase(base) {
        if (!base) return '';
        assertString(base, `Asset base: ${base}`);
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

    function resolveAssetPath(src) {
        assertString(src, `Asset path: ${src}`);
        if (/^[a-z][a-z0-9+.-]*:/i.test(src) || src.startsWith('//') || src.startsWith('/') || src.includes('..') || src.includes('\\')) {
            throw new Error(`Asset path must stay inside the data package: ${src}`);
        }
        return src;
    }

    function validateCondition(condition, ownerLabel) {
        if (condition === undefined || condition === null || condition === true || condition === false) {
            return;
        }
        if (Array.isArray(condition)) {
            condition.forEach(item => validateCondition(item, ownerLabel));
            return;
        }
        assertPlainObject(condition, `Condition for ${ownerLabel}`);

        if (condition.all !== undefined) {
            assert(Array.isArray(condition.all), `Condition.all for ${ownerLabel} must be an array`);
            condition.all.forEach(item => validateCondition(item, ownerLabel));
            return;
        }
        if (condition.any !== undefined) {
            assert(Array.isArray(condition.any), `Condition.any for ${ownerLabel} must be an array`);
            condition.any.forEach(item => validateCondition(item, ownerLabel));
            return;
        }
        if (condition.not !== undefined) {
            validateCondition(condition.not, ownerLabel);
            return;
        }

        assertString(condition.path, `Condition path for ${ownerLabel}`);
        safePathParts(condition.path);

        const op = condition.op || 'truthy';
        assert(CONDITION_OPS.has(op), `Unknown condition op for ${ownerLabel}: ${op}`);
        if ((op === '==' || op === '!=' || op === '>' || op === '>=' || op === '<' || op === '<=' || op === 'includes') && !('value' in condition)) {
            throw new Error(`Condition for ${ownerLabel} requires value`);
        }
    }

    function validateBlock(block, sceneId, index) {
        assertPlainObject(block, `Block ${sceneId}[${index}]`);
        assertString(block.type, `Block type for ${sceneId}[${index}]`);
        if (!BLOCK_TYPES.has(block.type)) {
            throw new Error(`Unsupported block type for ${sceneId}[${index}]: ${block.type}`);
        }

        if (block.type === 'dialogue') {
            assertString(block.speaker, `Dialogue speaker for ${sceneId}[${index}]`);
            assertString(block.content, `Dialogue content for ${sceneId}[${index}]`);
            return;
        }

        if (block.content !== undefined) {
            assertString(block.content, `Block content for ${sceneId}[${index}]`);
        }
        if (block.text !== undefined) {
            assertString(block.text, `Block text for ${sceneId}[${index}]`);
        }
        if (block.content === undefined && block.text === undefined) {
            throw new Error(`Block ${sceneId}[${index}] must include content or text`);
        }
    }

    function validateAction(action, sceneId, ownerLabel, context) {
        if (!action || !action.type) {
            throw new Error(`Action must include type: ${sceneId}/${ownerLabel}`);
        }
        if (!ACTION_TYPES.has(action.type)) {
            throw new Error(`Unknown action type: ${sceneId}/${ownerLabel} -> ${action.type}`);
        }

        if (action.type === 'goto' || action.type === 'ending') {
            assertString(action.target, `Action target for ${sceneId}/${ownerLabel}`);
            if (!context.sceneIds.has(action.target)) {
                throw new Error(`Action target not found: ${sceneId}/${ownerLabel} -> ${action.target}`);
            }
            if (context.ownerType === 'scene.onEnter' && action.target === sceneId) {
                throw new Error(`Scene onEnter cannot goto itself directly: ${sceneId}`);
            }
        }

        if (action.type === 'state.set' || action.type === 'state.add' || action.type === 'state.toggle' || action.type === 'state.push' || action.type === 'state.remove' || action.type === 'flag.set') {
            safePathParts(action.path);
        }

        if (action.type === 'state.add' && action.value !== undefined) {
            assertNumber(action.value, `state.add value for ${sceneId}/${ownerLabel}`);
        }

        if (action.type === 'item.add' || action.type === 'item.remove') {
            assertString(action.id, `Item id for ${sceneId}/${ownerLabel}`);
            const count = action.count === undefined ? 1 : action.count;
            assert(Number.isInteger(count) && count >= 0, `Item count for ${sceneId}/${ownerLabel} must be a non-negative integer`);
        }

        if (action.type === 'bgm.play') {
            const trackId = typeof action.id === 'string' && action.id.trim() ? action.id : action.track;
            assertString(trackId, `bgm.play id for ${sceneId}/${ownerLabel}`);
            if (!context.trackIds.has(trackId)) {
                throw new Error(`BGM track not found: ${sceneId}/${ownerLabel} -> ${trackId}`);
            }
            if (action.volume !== undefined) {
                assertRange(action.volume, 0, 1, `bgm.play volume for ${sceneId}/${ownerLabel}`);
            }
            if (action.loop !== undefined) {
                assertBoolean(action.loop, `bgm.play loop for ${sceneId}/${ownerLabel}`);
            }
            if (action.fadeIn !== undefined) {
                assertBoolean(action.fadeIn, `bgm.play fadeIn for ${sceneId}/${ownerLabel}`);
            }
            if (action.forceRestart !== undefined) {
                assertBoolean(action.forceRestart, `bgm.play forceRestart for ${sceneId}/${ownerLabel}`);
            }
        }

        if (action.type === 'notify') {
            assertString(action.message, `notify message for ${sceneId}/${ownerLabel}`);
        }

        if (action.type === 'theme.set') {
            const themeName = typeof action.theme === 'string' && action.theme.trim() ? action.theme : action.value;
            assertString(themeName, `theme.set value for ${sceneId}/${ownerLabel}`);
            if (!context.themeIds.has(themeName)) {
                throw new Error(`Theme not found: ${sceneId}/${ownerLabel} -> ${themeName}`);
            }
        }
    }

    function validateActionList(actions, sceneId, ownerLabel, context) {
        assert(Array.isArray(actions), `Actions for ${sceneId}/${ownerLabel} must be an array`);
        let sawTransition = false;
        actions.forEach((action, index) => {
            if (sawTransition) {
                throw new Error(`Scene transition action must be the last action: ${sceneId}/${ownerLabel}[${index}]`);
            }
            validateAction(action, sceneId, ownerLabel, context);
            if (TRANSITION_TYPES.has(action.type)) {
                sawTransition = true;
                if (context.sceneEdges && context.ownerType === 'scene.onEnter') {
                    context.sceneEdges.set(sceneId, action.target);
                }
            }
        });
    }

    function validateChoice(choice, sceneId, index, context) {
        assertPlainObject(choice, `Choice ${sceneId}[${index}]`);
        assertString(choice.id, `Choice id for ${sceneId}[${index}]`);
        assertString(choice.text, `Choice text for ${sceneId}[${index}]`);
        assert(Array.isArray(choice.actions), `Choice actions for ${sceneId}/${choice.id} must be an array`);
        validateCondition(choice.visibleWhen, `${sceneId}/${choice.id}.visibleWhen`);
        validateCondition(choice.disabledWhen, `${sceneId}/${choice.id}.disabledWhen`);
        validateActionList(choice.actions, sceneId, choice.id, {
            sceneIds: context.sceneIds,
            trackIds: context.trackIds,
            themeIds: context.themeIds,
            ownerType: 'choice'
        });
    }

    function detectOnEnterCycles(sceneEdges) {
        const visitState = new Map();
        const stack = [];

        const visit = sceneId => {
            const state = visitState.get(sceneId) || 0;
            if (state === 1) {
                const start = stack.indexOf(sceneId);
                const cycle = stack.slice(start).concat(sceneId);
                throw new Error(`onEnter goto cycle detected: ${cycle.join(' -> ')}`);
            }
            if (state === 2) return;

            visitState.set(sceneId, 1);
            stack.push(sceneId);

            const nextSceneId = sceneEdges.get(sceneId);
            if (nextSceneId) {
                visit(nextSceneId);
            }

            stack.pop();
            visitState.set(sceneId, 2);
        };

        sceneEdges.forEach((_, sceneId) => visit(sceneId));
    }

    function validateBundle(bundle) {
        assertPlainObject(bundle, 'Bundle');
        if (bundle.schemaVersion !== undefined) {
            assertString(bundle.schemaVersion, 'schemaVersion');
        }

        const game = bundle.game === undefined ? {} : bundle.game;
        const ui = bundle.ui === undefined ? {} : bundle.ui;
        const audio = bundle.audio === undefined ? {} : bundle.audio;
        const initialState = bundle.initialState === undefined ? {} : bundle.initialState;
        const scenes = bundle.scenes === undefined ? {} : bundle.scenes;
        const themes = bundle.themes === undefined ? [] : bundle.themes;

        assertPlainObject(game, 'game');
        assertPlainObject(ui, 'ui');
        assertPlainObject(audio, 'audio');
        assertPlainObject(initialState, 'initialState');
        assertPlainObject(scenes, 'scenes');
        assert(Array.isArray(themes), 'themes must be an array');

        if (game.id !== undefined) assertString(game.id, 'game.id');
        if (game.title !== undefined) assertString(game.title, 'game.title');
        if (game.subtitle !== undefined) assertString(game.subtitle, 'game.subtitle');
        if (game.startScene !== undefined) assertString(game.startScene, 'game.startScene');
        if (!game.startScene) throw new Error('Bundle missing game.startScene');
        if (game.defaultTheme !== undefined) assertString(game.defaultTheme, 'game.defaultTheme');
        if (game.assetBaseUrl !== undefined) resolveAssetBase(game.assetBaseUrl);

        if (ui.startButton !== undefined) assertString(ui.startButton, 'ui.startButton');
        if (ui.settingsButton !== undefined) assertString(ui.settingsButton, 'ui.settingsButton');
        if (ui.loadingText !== undefined) assertString(ui.loadingText, 'ui.loadingText');
        if (ui.welcome !== undefined) {
            assert(Array.isArray(ui.welcome), 'ui.welcome must be an array');
            ui.welcome.forEach((line, index) => assertString(line, `ui.welcome[${index}]`));
        }

        if (audio.defaultVolume !== undefined) {
            assertRange(audio.defaultVolume, 0, 1, 'audio.defaultVolume');
        }
        if (audio.tracks !== undefined) {
            assertPlainObject(audio.tracks, 'audio.tracks');
        }

        const declaredThemeIds = new Set();
        const themeIds = new Set(BUILTIN_THEME_IDS);
        themes.forEach((theme, index) => {
            assertPlainObject(theme, `Theme[${index}]`);
            assertString(theme.id, `Theme[${index}].id`);
            if (declaredThemeIds.has(theme.id)) {
                throw new Error(`Duplicate theme id: ${theme.id}`);
            }
            declaredThemeIds.add(theme.id);
            themeIds.add(theme.id);
            if (theme.label !== undefined) {
                assertString(theme.label, `Theme[${index}].label`);
            }
        });
        if (game.defaultTheme && !themeIds.has(game.defaultTheme)) {
            throw new Error(`Default theme not found: ${game.defaultTheme}`);
        }

        const trackIds = new Set();
        if (audio.tracks) {
            Object.entries(audio.tracks).forEach(([trackId, track]) => {
                if (trackIds.has(trackId)) {
                    throw new Error(`Duplicate BGM track id: ${trackId}`);
                }
                trackIds.add(trackId);
                assertPlainObject(track, `BGM track ${trackId}`);
                assertString(track.src, `BGM track src for ${trackId}`);
                resolveAssetPath(track.src);
                if (track.volume !== undefined) assertRange(track.volume, 0, 1, `BGM track volume for ${trackId}`);
                if (track.loop !== undefined) assertBoolean(track.loop, `BGM track loop for ${trackId}`);
                if (track.fadeIn !== undefined) assertBoolean(track.fadeIn, `BGM track fadeIn for ${trackId}`);
            });
        }

        const sceneIds = new Set(Object.keys(scenes));
        if (!sceneIds.has(game.startScene)) {
            throw new Error(`Start scene not found: ${game.startScene}`);
        }

        const sceneEdges = new Map();
        Object.entries(scenes).forEach(([sceneId, scene]) => {
            assertPlainObject(scene, `Scene ${sceneId}`);
            if (scene.id !== undefined) {
                assertString(scene.id, `Scene id for ${sceneId}`);
                if (scene.id !== sceneId) {
                    throw new Error(`Scene id must match its key: ${sceneId}`);
                }
            }
            if (scene.chapter !== undefined) assertString(scene.chapter, `Scene chapter for ${sceneId}`);
            if (scene.time !== undefined) assertString(scene.time, `Scene time for ${sceneId}`);
            if (scene.isEnding !== undefined) assertBoolean(scene.isEnding, `Scene isEnding for ${sceneId}`);

            if (scene.blocks !== undefined) {
                assert(Array.isArray(scene.blocks), `Scene blocks must be an array: ${sceneId}`);
                scene.blocks.forEach((block, index) => validateBlock(block, sceneId, index));
            }

            if (scene.onEnter !== undefined) {
                validateActionList(scene.onEnter, sceneId, 'onEnter', {
                    sceneIds,
                    trackIds,
                    themeIds,
                    ownerType: 'scene.onEnter',
                    sceneEdges
                });
            }

            if (scene.choices !== undefined) {
                assert(Array.isArray(scene.choices), `Scene choices must be an array: ${sceneId}`);
                const choiceIds = new Set();
                scene.choices.forEach((choice, index) => {
                    assertPlainObject(choice, `Choice ${sceneId}[${index}]`);
                    assertString(choice.id, `Choice id for ${sceneId}[${index}]`);
                    if (choiceIds.has(choice.id)) {
                        throw new Error(`Duplicate choice id in scene ${sceneId}: ${choice.id}`);
                    }
                    choiceIds.add(choice.id);
                    validateChoice(choice, sceneId, index, {
                        sceneIds,
                        trackIds,
                        themeIds
                    });
                });
            }
        });

        detectOnEnterCycles(sceneEdges);
        return bundle;
    }

    return {
        validateBundle,
        safePathParts,
        isPlainObject
    };
});
