(function () {
    "use strict";

    const pageConfig = {
        challengeUrl: document.body.dataset.eimzoChallengeUrl,
        verifyUrl: document.body.dataset.eimzoVerifyUrl,
        mahallaFieldId: document.body.dataset.mahallaId,
        usernameFieldId: document.body.dataset.usernameId,
    };

    const CAPI_URLS = [
        "/static/js/vendors/yt-capi-ws.js",
        "https://127.0.0.1:64646/CAPIWS.js",
        "https://localhost:64646/CAPIWS.js",
        "https://127.0.0.1:64446/CAPIWS.js",
        "https://localhost:64446/CAPIWS.js",
        "http://127.0.0.1:64646/CAPIWS.js",
        "http://localhost:64646/CAPIWS.js",
        "http://127.0.0.1:64446/CAPIWS.js",
        "http://localhost:64446/CAPIWS.js",
    ];

    let capiLoadPromise = null;
    let capiInitError = "";

    const API_KEYS = [
        "localhost", "96D0C1491615C82B9A54D9989779DF825B690748224C2B04F500F370D51827CE2644D8D4A82C18184D73AB8530BB8ED537269603F61DB0D03D2104ABF789970B",
        "127.0.0.1", "A7BCFA5D490B351BE0754130DF03A068F855DB4333D43921125B9CF2670EF6A40370C646B90401955E1F7BC9CDBF59CE0B2C5467D820BE189C845D0B79CFC96F",
        "null", "E0A205EC4E7B78BBB56AFF83A733A1BB9FD39D562E67978CC5E7D73B0951DB1954595A20672A63332535E13CC6EC1E1FC8857BB09E0855D7E76E411B6FA16E9D",
    ];

    const CAPI_TIMEOUTS = {
        default: 30000,
        listCertificates: 30000,
        loadKey: 90000,
        createPkcs7: 180000,
    };

    function getCookie(name) {
        const value = "; " + document.cookie;
        const parts = value.split("; " + name + "=");
        if (parts.length === 2) {
            return parts.pop().split(";").shift();
        }
        return "";
    }

    function toErrorMessage(error) {
        if (!error) return "Noma'lum xatolik";
        if (typeof error === "string") return error;
        if (typeof error === "object") {
            if (error.reason) return String(error.reason);
            if (error.message) return String(error.message);
            try {
                return JSON.stringify(error);
            } catch (_err) {
                return "Noma'lum xatolik";
            }
        }
        return String(error);
    }

    async function getChallenge() {
        const res = await fetch(pageConfig.challengeUrl, {
            credentials: "same-origin",
            headers: { "X-CSRFToken": getCookie("csrftoken") },
        });
        if (!res.ok) {
            throw new Error("Challenge olishda xatolik");
        }
        return res.json();
    }

    async function verifySignature(signature, cert, chain, certMeta) {
        const res = await fetch(pageConfig.verifyUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
                signature: signature,
                cert: cert,
                chain: chain,
                cert_meta: certMeta || null,
            }),
        });
        return res.json();
    }

    function loadScriptOnce(url, timeoutMs) {
        return new Promise(function (resolve, reject) {
            const script = document.createElement("script");
            script.src = url;
            script.async = true;

            let timer = setTimeout(function () {
                script.onload = null;
                script.onerror = null;
                reject(new Error("Script timeout: " + url));
            }, timeoutMs || 2500);

            script.onload = function () {
                clearTimeout(timer);
                resolve();
            };
            script.onerror = function () {
                clearTimeout(timer);
                reject(new Error("Script yuklanmadi: " + url));
            };
            document.head.appendChild(script);
        });
    }

    async function loadCapi() {
        if (window.CAPIWS && window.CAPIWS.callFunction) {
            return true;
        }
        if (capiLoadPromise) {
            return capiLoadPromise;
        }

        const eimzoStatus = document.getElementById("eimzoListContainer");
        const setLoadStatus = (msg) => {
            if (eimzoStatus) eimzoStatus.innerHTML = `<div style="text-align: center; padding: 20px; color: #6b7280;">
                <div class="spinner-border text-primary" role="status" style="width: 2rem; height: 2rem; margin-bottom: 10px;"></div>
                <br>${msg}
            </div>`;
        };

        const installApiKeys = function () {
            return new Promise(function (resolve) {
                window.CAPIWS.apikey(
                    API_KEYS,
                    function (_event, data) {
                        if (data && data.success) {
                            capiInitError = "";
                            resolve(true);
                            return;
                        }
                        capiInitError = toErrorMessage(data && data.reason ? data.reason : data);
                        resolve(false);
                    },
                    function (err) {
                        capiInitError = toErrorMessage(err);
                        resolve(false);
                    }
                );
            });
        };

        capiLoadPromise = (async function () {
            for (const url of CAPI_URLS) {
                setLoadStatus("Tekshirilmoqda: " + url);
                try {
                    await loadScriptOnce(url, 5000);
                    if (window.CAPIWS && window.CAPIWS.callFunction) {
                        const apikeyOk = await installApiKeys();
                        if (apikeyOk) {
                            return true;
                        }
                    }
                } catch (_err) {
                    // Keyingi portga o'tadi
                }
            }
            return false;
        })();

        return capiLoadPromise;
    }

    async function ensureCapi() {
        const ok = await loadCapi();
        if (!ok || !window.CAPIWS || !window.CAPIWS.callFunction) {
            capiLoadPromise = null;
            const statusBox = document.getElementById("eimzoStatus");
            const host = window.location.hostname || "noma'lum host";
            const apiKeyHint = capiInitError
                ? `<br><small style="color:#b91c1c;">API-KEY xabari: ${capiInitError}</small>`
                : "";
            if (statusBox) {
                statusBox.innerHTML =
                    '<div class="alert alert-warning py-2 small mb-0">' +
                    "<b>E-IMZO topilmadi!</b><br>" +
                    '1. <a href="https://esi.uz/download/e-imzo" target="_blank">Pluginni yuklab oling</a><br>' +
                    "2. Agar o'rnatilgan bo'lsa, " +
                    '<a href="https://127.0.0.1:64646" target="_blank" class="eimzo-trust-link">BU YERNI BOSING</a> ' +
                    'va ochilgan oynada <b>"Advanced" -> "Proceed to 127.0.0.1 (unsafe)"</b> tugmasini bosing.<br>' +
                    `3. Sayt <b>${host}</b> orqali ochilgan bo'lsa, API-KEY mos kelmasligi mumkin. Loginni <b>127.0.0.1</b> yoki <b>localhost</b> orqali ochib sinang.` +
                    apiKeyHint +
                    "</div>";
            }
            throw new Error(capiInitError || "E-IMZO Web Plugin topilmadi");
        }
    }

    async function callCapi(plugin, name, args, timeoutMs) {
        const fnArgs = Array.isArray(args) ? args : [];
        const timeoutByName = {
            list_all_certificates: CAPI_TIMEOUTS.listCertificates,
            list_certificates: CAPI_TIMEOUTS.listCertificates,
            load_key: CAPI_TIMEOUTS.loadKey,
            create_pkcs7: CAPI_TIMEOUTS.createPkcs7,
        };
        const timeout = timeoutMs || timeoutByName[name] || CAPI_TIMEOUTS.default;
        await ensureCapi();

        return new Promise(function (resolve, reject) {
            const timer = setTimeout(function () {
                reject(new Error(`E-IMZO javob bermadi (${plugin}.${name}, timeout ${Math.round(timeout / 1000)}s)`));
            }, timeout);

            window.CAPIWS.callFunction(
                {
                    plugin: plugin,
                    name: name,
                    arguments: fnArgs,
                },
                function (_event, data) {
                    clearTimeout(timer);
                    if (data && typeof data === "object" && Object.prototype.hasOwnProperty.call(data, "success") && data.success === false) {
                        reject(new Error(`${plugin}.${name}: ${toErrorMessage(data.reason || data)}`));
                        return;
                    }
                    resolve(data);
                },
                function (error) {
                    clearTimeout(timer);
                    reject(new Error(`${plugin}.${name}: ${toErrorMessage(error)}`));
                }
            );
        });
    }

    function unwrapResult(payload) {
        if (payload && typeof payload === "object") {
            if ("result" in payload) return payload.result;
            if ("data" in payload) return payload.data;
            if ("responseObject" in payload) return payload.responseObject;
        }
        return payload;
    }

    function normalizeCertList(payload, pluginName) {
        const val = unwrapResult(payload);
        let list = [];
        if (Array.isArray(val)) list = val;
        if (val && Array.isArray(val.certificates)) list = val.certificates;
        if (!pluginName) return list;
        return list.map(function (item) {
            if (item && typeof item === "object") {
                return Object.assign({}, item, { __plugin: pluginName });
            }
            return item;
        });
    }

    function getCertBase64(item) {
        return item.certificate_64 || item.certificate || item.cert || item.cert_64 || item.base64 || item.pem || null;
    }

    function getSerial(item) {
        return item.serialNumber || item.serial_number || item.sn || item.serial || null;
    }

    function getCertAlias(item) {
        return item.alias || item.keyAlias || item.subject || null;
    }


    function parseAliasKeyValues(aliasText) {
        const src = String(aliasText || "");
        const out = {};
        if (!src) return out;

        src.split(",").forEach(function (part) {
            const chunk = String(part || "").trim();
            if (!chunk) return;
            const eq = chunk.indexOf("=");
            if (eq <= 0) return;

            const key = chunk.slice(0, eq).trim().toLowerCase();
            const val = chunk.slice(eq + 1).trim();
            if (!key || !val) return;
            if (!(key in out)) out[key] = val;
        });

        return out;
    }

    function getAliasValue(item, keyName) {
        const alias = getCertAlias(item);
        const m = parseAliasKeyValues(alias);
        const key = String(keyName || "").trim().toLowerCase();
        return m[key] || "";
    }

    function normalizeAliasDate(value) {
        const raw = String(value || "").trim();
        if (!raw) return "";

        const m = raw.match(/^(\d{4})\.(\d{2})\.(\d{2})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
        if (!m) return raw;

        const hh = m[4] || "00";
        const mm = m[5] || "00";
        const ss = m[6] || "00";
        return `${m[1]}-${m[2]}-${m[3]}T${hh}:${mm}:${ss}`;
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function extractPinflFromText(text) {
        const t = String(text || "");
        const m = t.match(/\b\d{14}\b/);
        return m ? m[0] : "";
    }

    function cleanCandidateName(rawValue) {
        let value = String(rawValue || "").replace(/\s+/g, " ").trim();
        if (!value) return "";

        value = value
            .replace(/^['\"]+|['\"]+$/g, "")
            .replace(/^(CN|2\.5\.4\.3)\s*[=:]\s*/i, "")
            .replace(/^DS\d+\s*/i, "")
            .trim();

        if (!value) return "";
        if (value.includes("=")) return "";
        if (!/[A-Za-z\u0400-\u04FF]/.test(value)) return "";
        if (/^\d+$/.test(value)) return "";

        return value;
    }

    function extractCnFromSubject(text) {
        const t = String(text || "").trim();
        if (!t) return "";

        const cnPatterns = [
            /CN\s*=\s*"([^"]+)"/i,
            /CN\s*=\s*([^,;\/]+)/i,
            /2\.5\.4\.3\s*=\s*"([^"]+)"/i,
            /2\.5\.4\.3\s*=\s*([^,;\/]+)/i,
            /CN\s*:\s*([^,;\/]+)/i,
        ];

        for (const pattern of cnPatterns) {
            const match = t.match(pattern);
            if (!match) continue;
            const candidate = cleanCandidateName(match[1]);
            if (candidate) return candidate;
        }

        const surname = (t.match(/2\.5\.4\.4\s*=\s*([^,;\/]+)/i) || [])[1] || "";
        const givenName = (t.match(/2\.5\.4\.42\s*=\s*([^,;\/]+)/i) || [])[1] || "";
        const middleName = (t.match(/2\.5\.4\.43\s*=\s*([^,;\/]+)/i) || [])[1] || "";
        const combined = cleanCandidateName([surname, givenName, middleName].filter(Boolean).join(" "));
        if (combined) return combined;

        const normalized = t.replace(/\//g, ",");
        const chunks = normalized.split(/[;,]/);
        for (const chunk of chunks) {
            const part = String(chunk || "").trim();
            if (!part) continue;
            const m = part.match(/^(CN|2\.5\.4\.3)\s*[=:]\s*(.+)$/i);
            if (!m) continue;
            const candidate = cleanCandidateName(m[2]);
            if (candidate) return candidate;
        }

        return "";
    }

    function getPinfl(item) {
        const directValues = [
            item.pinfl,
            item.PINFL,
            item.uid,
            item.UID,
            item.personalNumber,
            item.personal_number,
        ];

        for (const v of directValues) {
            const pinfl = extractPinflFromText(v);
            if (pinfl) return pinfl;
        }

        const textValues = [
            item.subject,
            item.subjectName,
            item.subject_name,
            item.subjectInfo,
            item.subject_info,
            item.owner,
            item.fullName,
            item.full_name,
            item.cn,
            item.CN,
            item.name,
            item.alias,
            getSerial(item),
        ];

        for (const t of textValues) {
            const pinfl = extractPinflFromText(t);
            if (pinfl) return pinfl;
        }

        return "";
    }

    function getCertDisplayName(item) {
        const direct = [
            item.fio,
            item.FIO,
            item.full_name,
            item.fullName,
            item.displayName,
            item.cn,
            item.CN,
            item.commonName,
            item.owner,
        ];

        for (const v of direct) {
            const candidate = cleanCandidateName(v);
            if (candidate) return candidate;
        }

        const aliasCn = cleanCandidateName(getAliasValue(item, "cn"));
        if (aliasCn) return aliasCn;

        const aliasFio = cleanCandidateName([
            getAliasValue(item, "surname"),
            getAliasValue(item, "name"),
            getAliasValue(item, "patronymic"),
        ].filter(Boolean).join(" "));
        if (aliasFio) return aliasFio;

        const subjects = [
            item.subject,
            item.subjectName,
            item.subject_name,
            item.subjectInfo,
            item.subject_info,
        ];

        for (const subj of subjects) {
            const subjectName = extractCnFromSubject(subj);
            if (subjectName) return subjectName;
        }

        const fallback = String(item.name || item.alias || "").trim();
        if (fallback) {
            const cleaned = cleanCandidateName(fallback.replace(/^DS\d+\s*/i, ""));
            if (cleaned) return cleaned;
        }

        return "F.I.Sh topilmadi";
    }

    function getCertValidTo(item) {
        return item.validTo || item.valid_to || item.notAfter || item.not_after || normalizeAliasDate(getAliasValue(item, "validto")) || "";
    }

    function buildCertMeta(item) {
        const displayName = getCertDisplayName(item);
        return {
            cn: displayName === "F.I.Sh topilmadi" ? "" : displayName,
            pinfl: getPinfl(item),
            subject: item.subject || item.subjectName || item.subject_name || item.subjectInfo || item.subject_info || "",
            serial: String(getSerial(item) || ""),
            valid_from: item.validFrom || item.valid_from || item.notBefore || item.not_before || null,
            valid_to: getCertValidTo(item) || null,
        };
    }

    function getCertPlugin(item) {
        return item.__plugin || item.plugin || null;
    }

    function getDiskPathName(item) {
        return {
            disk: item.disk || item.storage || item.drive || null,
            path: item.path || item.storagePath || "",
            name: item.name || item.alias || item.fileName || item.file_name || null,
        };
    }

    function buildLoadKeyArgs(pluginUsed, certItem) {
        const diskPathName = getDiskPathName(certItem);
        const serialNumber = getSerial(certItem);
        const alias = getCertAlias(certItem);

        if (!diskPathName.disk || !diskPathName.name) {
            throw new Error("Sertifikat disk yoki nom ma'lumoti topilmadi");
        }

        // pfx.load_key uchun 4-parametr alias bo'lishi kerak.
        if (pluginUsed === "pfx") {
            if (!alias) {
                throw new Error("PFX sertifikat alias topilmadi");
            }
            return [diskPathName.disk, diskPathName.path || "", diskPathName.name, alias];
        }

        if (!serialNumber) {
            throw new Error("Sertifikat seriya raqami topilmadi");
        }

        return [diskPathName.disk, diskPathName.path || "", diskPathName.name, serialNumber];
    }

    async function loadKeyForCert(certItem, statusCb) {
        const setStatus = typeof statusCb === "function" ? statusCb : function () { };
        let pluginUsed = getCertPlugin(certItem) || "pfx";

        setStatus("Kalit yuklanmoqda...");
        const loadArgs = buildLoadKeyArgs(pluginUsed, certItem);
        let loadResp;

        try {
            loadResp = await callCapi(pluginUsed, "load_key", loadArgs);
        } catch (err) {
            // Ba'zi versiyalarda certkey ma'lumotlari pfx pluginida ham ishlashi mumkin.
            if (pluginUsed !== "pfx") {
                pluginUsed = "pfx";
                const fallbackArgs = buildLoadKeyArgs(pluginUsed, certItem);
                loadResp = await callCapi(pluginUsed, "load_key", fallbackArgs);
            } else {
                throw err;
            }
        }

        const loadRes = unwrapResult(loadResp);
        const keyId = (loadRes && (loadRes.id || loadRes.keyId || loadRes.pfxId)) || loadRes;
        if (!keyId) {
            throw new Error("Parol xato yoki kalit yuklanmadi");
        }

        return { keyId: keyId, pluginUsed: pluginUsed };
    }

    function toBase64Utf8(text) {
        return btoa(unescape(encodeURIComponent(text)));
    }

    // Kalitlarni tanlash modali
    const eimzoModal = document.getElementById("eimzoModal");
    const closeEimzoModalBtn = document.getElementById("closeEimzoModal");
    const cancelEimzoBtn = document.getElementById("cancelEimzoBtn");
    const eimzoListContainer = document.getElementById("eimzoListContainer");
    const eimzoErrorBox = document.getElementById("eimzoErrorBox");

    function showModal() {
        if (eimzoModal) eimzoModal.style.display = "flex";
    }

    function hideModal() {
        if (eimzoModal) eimzoModal.style.display = "none";
    }

    if (closeEimzoModalBtn) closeEimzoModalBtn.addEventListener("click", hideModal);
    if (cancelEimzoBtn) cancelEimzoBtn.addEventListener("click", hideModal);

    function getCertValidFrom(item) {
        return item.validFrom || item.valid_from || item.notBefore || item.not_before || normalizeAliasDate(getAliasValue(item, "validfrom")) || "";
    }

    function formatDateForUi(value) {
        if (!value) return "";
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return String(value);
        const day = String(d.getDate()).padStart(2, "0");
        const month = String(d.getMonth() + 1).padStart(2, "0");
        const year = d.getFullYear();
        return `${day}.${month}.${year}`;
    }

    function toDateSafe(value) {
        if (!value) return null;

        const raw = String(value).trim();
        const iso = new Date(raw);
        if (!Number.isNaN(iso.getTime())) return iso;

        const dotDmy = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
        if (dotDmy) {
            const d = new Date(Number(dotDmy[3]), Number(dotDmy[2]) - 1, Number(dotDmy[1]), 23, 59, 59);
            if (!Number.isNaN(d.getTime())) return d;
        }

        const dotYmd = raw.match(/^(\d{4})\.(\d{2})\.(\d{2})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
        if (dotYmd) {
            const hh = Number(dotYmd[4] || 23);
            const mm = Number(dotYmd[5] || 59);
            const ss = Number(dotYmd[6] || 59);
            const d = new Date(Number(dotYmd[1]), Number(dotYmd[2]) - 1, Number(dotYmd[3]), hh, mm, ss);
            if (!Number.isNaN(d.getTime())) return d;
        }

        return null;
    }

    function getCertCnName(item) {
        const directCn = cleanCandidateName(item.cn || item.CN || item.commonName || "");
        if (directCn) return directCn;

        const subjects = [
            item.subject,
            item.subjectName,
            item.subject_name,
            item.subjectInfo,
            item.subject_info,
        ];

        for (const subj of subjects) {
            const cn = extractCnFromSubject(subj);
            if (cn) return cn;
        }

        return "";
    }

    function isCertExpired(item) {
        const validToDate = toDateSafe(getCertValidTo(item));
        if (!validToDate) return false;
        return validToDate.getTime() < Date.now();
    }

    function collectCertVisibleInfo(item) {
        const subject = item.subject || item.subjectName || item.subject_name || item.subjectInfo || item.subject_info || "";
        const validFrom = getCertValidFrom(item);
        const validTo = getCertValidTo(item);
        const diskPath = [item.disk || item.storage || item.drive || "", item.path || item.storagePath || ""].filter(Boolean).join(" /");

        const rows = [
            ["Plugin", getCertPlugin(item) || ""],
            ["FIO (aniqlangan)", getCertDisplayName(item)],
            ["PINFL (aniqlangan)", getPinfl(item)],
            ["Serial", getSerial(item) || ""],
            ["Alias", item.alias || item.keyAlias || ""],
            ["Name", item.name || item.fileName || item.file_name || ""],
            ["Disk/Path", diskPath],
            ["Amal boshlanishi", formatDateForUi(validFrom)],
            ["Amal tugashi", formatDateForUi(validTo)],
            ["Subject", subject],
            ["Certificate(base64)", getCertBase64(item) ? "Mavjud" : "Yo'q"],
        ];

        const knownKeys = new Set([
            "__plugin", "plugin", "subject", "subjectName", "subject_name", "subjectInfo", "subject_info",
            "validFrom", "valid_from", "notBefore", "not_before", "validTo", "valid_to", "notAfter", "not_after",
            "disk", "storage", "drive", "path", "storagePath",
            "serialNumber", "serial_number", "sn", "serial",
            "alias", "keyAlias", "name", "fileName", "file_name",
            "certificate_64", "certificate", "cert", "cert_64", "base64", "pem",
            "pinfl", "PINFL", "uid", "UID", "personalNumber", "personal_number",
            "fio", "FIO", "full_name", "fullName", "displayName", "cn", "CN", "commonName", "owner",
        ]);

        Object.keys(item || {}).sort().forEach(function (k) {
            if (knownKeys.has(k)) return;
            const v = item[k];
            if (v === null || v === undefined) return;
            if (typeof v === "object") return;
            rows.push([`extra.${k}`, String(v)]);
        });

        return rows.filter(function (row) {
            return String(row[1] || "").trim() !== "";
        });
    }

    function renderCerts(certs) {
        if (!certs || certs.length === 0) {
            eimzoListContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #ef4444;">E-imzo kalitlari topilmadi. USB fleshka ulanmagan yoki E-imzo dasturi ishga tushmagan.</div>';
            return;
        }

        if (cancelEimzoBtn && cancelEimzoBtn.parentElement) {
            cancelEimzoBtn.parentElement.style.display = 'none';
        }

        eimzoListContainer.innerHTML = `
            <div id="eimzoDropdownWrap" style="border:1px solid #e5e7eb; border-radius:12px; background:#f8fafc; padding:12px;">
                <div style="position:relative;">
                    <button type="button" id="eimzoDropdownBtn" style="width:100%; text-align:left; border:1px solid #2563eb; border-radius:10px; background:#f3f4f6; padding:10px; cursor:pointer;">
                        <div id="eimzoSelectedCard"></div>
                        <div style="position:absolute; right:12px; top:12px; color:#6b7280; font-size:13px;">&#9662;</div>
                    </button>

                    <div id="eimzoDropdownList" style="display:none; position:absolute; left:0; right:0; top:calc(100% + 6px); z-index:5; background:#fff; border:1px solid #cbd5e1; border-radius:10px; max-height:280px; overflow:auto; box-shadow:0 10px 25px rgba(15,23,42,0.12);"></div>
                </div>

                <div style="display:flex; gap:10px; margin-top:12px;">
                    <button type="button" id="eimzoSignBtn" style="flex:1; padding:10px 12px; border:1px solid #0f3ea9; background:#0f3ea9; color:#fff; border-radius:10px; cursor:pointer; font-size:14px; font-weight:700;">Kirish</button>
                    <button type="button" id="eimzoCancelInlineBtn" style="padding:10px 12px; border:1px solid #cbd5e1; background:#fff; color:#334155; border-radius:10px; cursor:pointer; font-size:14px; font-weight:600;">Bekor qilish</button>
                </div>

                <div id="eimzoSignStatus" style="margin-top:8px; font-size:12px; color:#16a34a; min-height:18px;"></div>
            </div>`;

        const wrapEl = document.getElementById('eimzoDropdownWrap');
        const dropdownBtn = document.getElementById('eimzoDropdownBtn');
        const selectedCardEl = document.getElementById('eimzoSelectedCard');
        const listEl = document.getElementById('eimzoDropdownList');
        const signBtn = document.getElementById('eimzoSignBtn');
        const cancelInlineBtn = document.getElementById('eimzoCancelInlineBtn');
        const signStatusEl = document.getElementById('eimzoSignStatus');

        let selectedIdx = certs.findIndex(function (cert) {
            return !isCertExpired(cert);
        });

        const cardHtml = function (cert, active, expired) {
            const fio = getCertDisplayName(cert).toLocaleUpperCase('uz-UZ');
            const pinfl = getPinfl(cert) || 'Topilmadi';
            const serial = getSerial(cert) || cert.name || cert.alias || 'Topilmadi';
            const valFrom = formatDateForUi(getCertValidFrom(cert));
            const valTo = formatDateForUi(getCertValidTo(cert));
            const validityRange = valFrom && valTo
                ? `${valFrom} - ${valTo}`
                : (valTo || valFrom || 'Topilmadi');

            const borderColor = expired ? '#ef4444' : (active ? '#2563eb' : '#e5e7eb');
            const bgColor = expired ? '#fef2f2' : (active ? '#eff6ff' : '#ffffff');
            const titleColor = expired ? '#991b1b' : '#003893';

            return `
                <div style="border:1px solid ${borderColor}; border-radius:10px; background:${bgColor}; padding:10px; margin-bottom:8px;">
                    <div style="font-weight:700; color:${titleColor}; font-size:16px; line-height:1.2; margin-bottom:6px; word-break:break-word;">${escapeHtml(fio)}</div>
                    <div style="display:flex; gap:10px; flex-wrap:wrap; font-size:12px; color:#334155;">
                        <span>PINFL: <b>${escapeHtml(pinfl)}</b></span>
                        <span>Seriya: <b>${escapeHtml(serial)}</b></span>
                        <span>Muddati: <b>${escapeHtml(validityRange)}</b></span>
                    </div>
                    ${expired ? "<div style=\"margin-top:6px; font-size:12px; color:#b91c1c; font-weight:700;\">Muddati o'tgan kalit</div>" : ''}
                </div>`;
        };

        const renderSelected = function () {
            if (!certs.length) {
                selectedCardEl.innerHTML = '<div style="font-size:12px; color:#ef4444;">Kalit tanlanmagan</div>';
                return;
            }

            const idx = selectedIdx >= 0 ? selectedIdx : 0;
            const cert = certs[idx];
            const expired = isCertExpired(cert);
            selectedCardEl.innerHTML = cardHtml(cert, selectedIdx >= 0, expired);

            if (selectedIdx < 0) {
                selectedCardEl.innerHTML += "<div style=\"font-size:12px; color:#b91c1c; font-weight:700;\">Muddati o'tmagan kalit topilmadi</div>";
            }
        };

        const renderList = function () {
            listEl.innerHTML = certs.map(function (cert, idx) {
                const expired = isCertExpired(cert);
                return `<button type="button" class="eimzo-cert-option" data-index="${idx}" ${expired ? 'disabled' : ''} style="display:block; width:100%; text-align:left; border:0; background:transparent; padding:8px; cursor:${expired ? 'not-allowed' : 'pointer'}; opacity:${expired ? '0.82' : '1'};">${cardHtml(cert, idx === selectedIdx, expired)}</button>`;
            }).join('');
        };

        const closeList = function () {
            listEl.style.display = 'none';
        };

        dropdownBtn.addEventListener('click', function () {
            listEl.style.display = (listEl.style.display === 'none' || !listEl.style.display) ? 'block' : 'none';
        });

        listEl.addEventListener('click', function (event) {
            const opt = event.target.closest('.eimzo-cert-option');
            if (!opt) return;
            const idx = parseInt(opt.getAttribute('data-index'), 10);
            if (Number.isNaN(idx) || !certs[idx] || isCertExpired(certs[idx])) return;

            selectedIdx = idx;
            renderSelected();
            renderList();
            closeList();

            if (signStatusEl) signStatusEl.textContent = '';
            if (eimzoErrorBox) eimzoErrorBox.style.display = 'none';
            signBtn.disabled = false;
            signBtn.style.opacity = '1';
        });

        document.addEventListener('click', function (event) {
            if (!wrapEl.contains(event.target)) closeList();
        });

        cancelInlineBtn.addEventListener('click', function () {
            hideModal();
        });

        signBtn.addEventListener('click', async function () {
            const selectedCert = selectedIdx >= 0 ? certs[selectedIdx] : null;
            if (!selectedCert || isCertExpired(selectedCert)) {
                eimzoErrorBox.innerHTML = "Muddati o'tgan kalit bilan kirib bo'lmaydi";
                eimzoErrorBox.style.display = 'block';
                return;
            }

            signBtn.disabled = true;
            cancelInlineBtn.disabled = true;
            dropdownBtn.disabled = true;
            signBtn.style.opacity = '0.7';
            eimzoErrorBox.style.display = 'none';

            const setStatusLog = function (msg) {
                if (signStatusEl) signStatusEl.textContent = msg;
            };

            try {
                const challenge = await getChallenge();
                const signResult = await signSelectedCertWithEimzo(challenge.nonce, selectedCert, setStatusLog);

                setStatusLog('Backend orgali tekshirilmoqda...');
                const result = await verifySignature(signResult.signature, signResult.cert || null, signResult.chain || null, signResult.cert_meta || null);

                if (result.ok) {
                    setStatusLog('Muvaffaqiyatli! Tizimga kirilmoqda...');
                    window.location.href = result.redirect || '/';
                } else {
                    eimzoErrorBox.innerHTML = result.error || 'Backend xatoligi yuz berdi';
                    eimzoErrorBox.style.display = 'block';
                    setStatusLog('');
                    signBtn.disabled = false;
                    cancelInlineBtn.disabled = false;
                    dropdownBtn.disabled = false;
                    signBtn.style.opacity = '1';
                }
            } catch (err) {
                eimzoErrorBox.innerHTML = err.message || 'Xatolik yuz berdi';
                eimzoErrorBox.style.display = 'block';
                setStatusLog('');
                signBtn.disabled = false;
                cancelInlineBtn.disabled = false;
                dropdownBtn.disabled = false;
                signBtn.style.opacity = '1';
            }
        });

        renderSelected();
        renderList();

        if (selectedIdx < 0) {
            signBtn.disabled = true;
            signBtn.style.opacity = '0.6';
            if (signStatusEl) signStatusEl.textContent = "Barcha kalitlar muddati o'tgan";
        }
    }

    async function signSelectedCertWithEimzo(nonce, certItem, statusCb) {
        const setStatus = typeof statusCb === "function" ? statusCb : function () { };
        const keyMeta = await loadKeyForCert(certItem, setStatus);
        const keyId = keyMeta.keyId;

        const nonce64 = toBase64Utf8(nonce);
        const createPkcs7 = async function (detachedFlag) {
            const signResp = await callCapi("pkcs7", "create_pkcs7", [nonce64, keyId, detachedFlag], CAPI_TIMEOUTS.createPkcs7);
            const signRes = unwrapResult(signResp);
            return (signRes && (signRes.pkcs7_64 || signRes.pkcs7 || signRes.signature)) || signRes;
        };

        setStatus("Imzo yaratilmoqda (PKCS7)... Parol oynasi chiqsa tasdiqlang.");
        let signature = null;
        try {
            signature = await createPkcs7("yes");
        } catch (err) {
            const msg = (err && err.message) ? err.message : "";
            if (msg.toLowerCase().includes("timeout")) {
                setStatus("PKCS7 timeout bo'ldi, qayta urinilmoqda...");
                signature = await createPkcs7("no");
            } else {
                throw err;
            }
        }

        if (typeof signature !== "string") {
            throw new Error("Imzolash bekor qilindi yoki imzo olinmadi");
        }

        signature = signature.trim();
        if (!signature) {
            throw new Error("Imzolash bekor qilindi yoki imzo olinmadi");
        }

        try { await callCapi(keyMeta.pluginUsed, "unload_key", [keyId], 20000); } catch (_err) { }

        let cert64 = getCertBase64(certItem);
        let chain = null;
        const certMeta = buildCertMeta(certItem);
        return { signature: signature, cert: cert64, chain: chain, cert_meta: certMeta };
    }

    async function handleEimzoLogin() {
        showModal();
        if (cancelEimzoBtn && cancelEimzoBtn.parentElement) cancelEimzoBtn.parentElement.style.display = '';
        if (eimzoErrorBox) eimzoErrorBox.style.display = 'none';
        renderModeChoice();
    }

    function renderModeChoice() {
        eimzoListContainer.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:10px;">
                <button type="button" id="choosePfxModeBtn" style="padding:12px; border:1px solid #0f3ea9; background:#0f3ea9; color:#fff; border-radius:10px; cursor:pointer; font-weight:700;">PFX fayl bilan kirish</button>
                <button type="button" id="chooseCapiModeBtn" style="padding:12px; border:1px solid #cbd5e1; background:#fff; color:#334155; border-radius:10px; cursor:pointer; font-weight:600;">E-IMZO dasturi orqali</button>
            </div>`;
        document.getElementById('choosePfxModeBtn').addEventListener('click', renderPfxForm);
        document.getElementById('chooseCapiModeBtn').addEventListener('click', startCapiFlow);
    }

    function renderPfxForm() {
        if (eimzoErrorBox) eimzoErrorBox.style.display = 'none';
        eimzoListContainer.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:6px;">
                <label for="pfxFileInput" style="font-size:13px; font-weight:600; color:#334155;">Kalit fayli (.pfx / .p12)</label>
                <input type="file" id="pfxFileInput" accept=".pfx,.p12,application/x-pkcs12" style="font-size:13px; border:1px solid #cbd5e1; border-radius:8px; padding:8px;">
                <label for="pfxPasswordInput" style="font-size:13px; font-weight:600; color:#334155; margin-top:6px;">Kalit paroli</label>
                <input type="password" id="pfxPasswordInput" autocomplete="off" style="border:1px solid #cbd5e1; border-radius:8px; padding:10px; font-size:14px;">
                <button type="button" id="pfxSubmitBtn" style="margin-top:10px; padding:10px 12px; border:1px solid #0f3ea9; background:#0f3ea9; color:#fff; border-radius:10px; cursor:pointer; font-size:14px; font-weight:700;">Kirish</button>
                <button type="button" id="pfxBackBtn" style="padding:8px 12px; border:1px solid #cbd5e1; background:#fff; color:#334155; border-radius:10px; cursor:pointer; font-size:13px;">Orqaga</button>
                <div id="pfxStatusEl" style="font-size:12px; color:#16a34a; min-height:16px;"></div>
            </div>`;
        document.getElementById('pfxBackBtn').addEventListener('click', renderModeChoice);
        document.getElementById('pfxSubmitBtn').addEventListener('click', submitPfxLogin);
    }

    async function submitPfxLogin() {
        const fileInput = document.getElementById('pfxFileInput');
        const passInput = document.getElementById('pfxPasswordInput');
        const statusEl = document.getElementById('pfxStatusEl');
        const submitBtn = document.getElementById('pfxSubmitBtn');
        const setStatus = (m) => { if (statusEl) statusEl.textContent = m; };
        const fail = (msg) => {
            eimzoErrorBox.innerHTML = escapeHtml(msg || 'Xatolik yuz berdi');
            eimzoErrorBox.style.display = 'block';
            setStatus('');
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
        };

        if (!fileInput.files || fileInput.files.length === 0) {
            fail('Kalit faylini tanlang');
            return;
        }
        const file = fileInput.files[0];
        if (file.size > 100 * 1024) {
            fail('Fayl hajmi juda katta (maks 100 KB)');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.7';

        try {
            setStatus("Fayl o'qilmoqda...");
            const buf = await file.arrayBuffer();
            const bytes = new Uint8Array(buf);
            let binary = '';
            for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
            const pfxB64 = btoa(binary);

            setStatus('Challenge olinmoqda...');
            const challenge = await getChallenge();

            setStatus('Serverda imzolanmoqda va tekshirilmoqda...');
            const res = await fetch(pageConfig.verifyUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ pfx_b64: pfxB64, password: passInput.value }),
            });
            const result = await res.json();

            if (result.ok) {
                setStatus('Muvaffaqiyatli! Tizimga kirilmoqda...');
                window.location.href = result.redirect || '/';
            } else {
                fail(result.error || 'Backend xatoligi yuz berdi');
            }
        } catch (err) {
            fail(err.message || 'Xatolik yuz berdi');
        }
    }

    async function startCapiFlow() {
        eimzoListContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #6b7280;">Dasturga bog\'lanilmoqda...</div>';

        try {
            await ensureCapi();

            let certs = [];

            // 1. Smart-karta/tokendagi kalitlar
            try {
                const certkeyResp = await callCapi("certkey", "list_all_certificates", []);
                certs = certs.concat(normalizeCertList(certkeyResp, "certkey"));
            } catch (_err) {
                // ignore
            }

            // 2. PFX sertifikatlar
            try {
                const pfxResp = await callCapi("pfx", "list_all_certificates", []);
                certs = certs.concat(normalizeCertList(pfxResp, "pfx"));
            } catch (_err) {
                // Ayrim versiyalarda disk bo'yicha fallback ishlatiladi.
                try {
                    const disksResp = await callCapi("pfx", "list_disks", []);
                    const disks = unwrapResult(disksResp);
                    if (Array.isArray(disks)) {
                        for (let item of disks) {
                            const d = item.disk || item;
                            if (!d) continue;
                            try {
                                const rootCerts = await callCapi("pfx", "list_certificates", [d, ""]);
                                certs = certs.concat(normalizeCertList(rootCerts, "pfx"));
                            } catch (_innerErr) { }
                            try {
                                const dsCerts = await callCapi("pfx", "list_certificates", [d, "DSKEYS"]);
                                certs = certs.concat(normalizeCertList(dsCerts, "pfx"));
                            } catch (_innerErr) { }
                        }
                    }
                } catch (_innerErr) {
                    // ignore
                }
            }

            // Takroriy sertifikatlarni filtrlash
            const uniqueCerts = [];
            const seen = new Set();
            certs.forEach(c => {
                const key = [
                    getCertPlugin(c) || "",
                    getSerial(c) || "",
                    getCertAlias(c) || "",
                    c.disk || "",
                    c.path || "",
                    c.name || "",
                ].join("_");
                if (!seen.has(key)) {
                    seen.add(key);
                    uniqueCerts.push(c);
                }
            });

            renderCerts(uniqueCerts);

        } catch (_err) {
            eimzoErrorBox.innerHTML = `
                <b>E-IMZO bilan bog'lanishda xatolik.</b><br>
                E-IMZO ilovasi ishlayotganiga (kompyuterning o'ng quyi burchagida qanotli ikonka borligiga) ishonch hosil qiling.<br><br>
                <i>Agar ishlayotgan bo'lsa, brauzer havfsizlik uchun to'sayotgan bo'lishi mumkin:</i><br>
                <a href="https://127.0.0.1:64646" target="_blank" style="color: #0284c7; text-decoration: underline;">BU YERNI BOSING</a> va yangi ochilgan oynada <b>"Advanced"</b> -> <b>"Proceed"</b> tugmasini bosing. So'ng sahifani yangilang.<br><br>
                <i>Agar sayt IP yoki domen orqali ochilgan bo'lsa, API-KEY sababli ishlamasligi mumkin. Imkon bo'lsa login sahifasini <b>127.0.0.1</b> yoki <b>localhost</b> orqali oching.</i>
            `;
            eimzoErrorBox.style.display = 'block';
            eimzoListContainer.innerHTML = '';
        }
    }

    function setupAdminLoginToggle() {
        const mahallaEl = pageConfig.mahallaFieldId ? document.getElementById(pageConfig.mahallaFieldId) : null;
        const usernameEl = pageConfig.usernameFieldId ? document.getElementById(pageConfig.usernameFieldId) : null;
        const adminLoginGroup = document.getElementById("adminLoginGroup");
        const adminLoginDivider = document.getElementById("adminLoginDivider");

        if (!mahallaEl) {
            return;
        }

        function toggleAdminLogin() {
            const hasMahalla = Boolean(mahallaEl.value && mahallaEl.value.trim() !== "");
            if (adminLoginGroup) adminLoginGroup.style.display = hasMahalla ? "none" : "";
            if (adminLoginDivider) adminLoginDivider.style.display = hasMahalla ? "none" : "";
            if (hasMahalla && usernameEl) usernameEl.value = "";
        }

        mahallaEl.addEventListener("change", toggleAdminLogin);
        toggleAdminLogin();
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!pageConfig.challengeUrl || !pageConfig.verifyUrl) {
            console.warn("E-IMZO endpointlari topilmadi");
            return;
        }

        const eimzoButton = document.getElementById("eimzoLoginBtn");
        if (eimzoButton) {
            eimzoButton.addEventListener("click", handleEimzoLogin);
        }

        setupAdminLoginToggle();
    });
})();




