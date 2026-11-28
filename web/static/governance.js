/* ==========================================================================
   CAMADA DE GOVERNANÇA (PocGov) — login opcional, painel de governança e
   integração do editor 3D com as propostas (cópia de trabalho por branch Git).

   Visitante (sem login): explora, cria e edita no editor, mas nada é salvo;
   um F5 perde tudo (o estado vive só na memória da página).
   ========================================================================== */
(function () {
    "use strict";

    const OntoGov = (window.OntoGov = {
        auth: { user: null, permissions: [] },
        meta: null,
        context: null,       // proposta/versão aberta no editor
        loadedExport: null   // export do editor logo após carregar (base do delta enviado ao servidor)
    });

    const esc = (v) => escapeHtml(v);
    const $ = (id) => document.getElementById(id);
    const can = (perm) => OntoGov.auth.permissions.includes(perm);
    const state = { tab: "ontologias", ontologies: [], view: null, filters: { ontology: "", status: "", mine: false } };

    const STATUS_CLASS = {
        pendente: "st-pend", em_analise: "st-anal", inconsistente: "st-err", em_validacao: "st-val",
        aguardando_ajustes: "st-warn", aprovada: "st-ok", rejeitada: "st-rej", publicada: "st-pub"
    };
    const EDIT_STATUSES = ["em_analise", "inconsistente", "aguardando_ajustes"];

    // ------------------------------------------------------------------
    // API
    // ------------------------------------------------------------------
    async function api(method, path, body) {
        const resp = await fetch(path, {
            method,
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-OntoCube": "1" },
            body: body === undefined ? undefined : JSON.stringify(body)
        });
        const isJson = (resp.headers.get("content-type") || "").includes("json");
        const data = isJson ? await resp.json() : await resp.text();
        if (!resp.ok) {
            const err = new Error((data && data.error) || `Erro ${resp.status}`);
            err.status = resp.status;
            if (resp.status === 401) refreshAuth();
            throw err;
        }
        return data;
    }

    function fmtDate(v) {
        if (!v) return "—";
        const d = new Date(v);
        return isNaN(d) ? esc(v) : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
    }

    function statusChip(status) {
        const label = (OntoGov.meta && OntoGov.meta.statuses[status]) || status;
        return `<span class="st-chip ${STATUS_CLASS[status] || ""}">${esc(label)}</span>`;
    }

    function shortIri(iri) {
        return esc(localName(iri) || iri);
    }

    // Markdown mínimo (títulos, listas, tabelas, código, negrito) — entrada sempre escapada
    function renderMarkdown(md) {
        const lines = String(md || "").replace(/\r/g, "").split("\n");
        const out = [];
        let i = 0;
        const inline = (t) =>
            esc(t)
                .replace(/`([^`]+)`/g, "<code>$1</code>")
                .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
                .replace(/_([^_]+)_/g, "<em>$1</em>");
        while (i < lines.length) {
            const line = lines[i];
            if (line.startsWith("```")) {
                const buf = [];
                i++;
                while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
                i++;
                out.push(`<pre class="md-code">${esc(buf.join("\n"))}</pre>`);
                continue;
            }
            const h = line.match(/^(#{1,4})\s+(.*)$/);
            if (h) {
                out.push(`<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`);
                i++;
                continue;
            }
            if (line.trim().startsWith("|")) {
                const rows = [];
                while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
                const cells = (r) => r.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map((c) => c.replace(/\\\|/g, "|").trim());
                const body = rows.filter((r, idx) => !(idx === 1 && /^\s*\|?\s*:?-{2,}/.test(r)));
                const [head, ...rest] = body;
                out.push(
                    `<div class="table-scroll"><table class="gov-table"><thead><tr>${cells(head).map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>` +
                        rest.map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") +
                        "</tbody></table></div>"
                );
                continue;
            }
            if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
                const ordered = /^\s*\d+\./.test(line);
                const items = [];
                while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
                    items.push(`<li>${inline(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""))}</li>`);
                    i++;
                }
                out.push(ordered ? `<ol>${items.join("")}</ol>` : `<ul>${items.join("")}</ul>`);
                continue;
            }
            if (line.trim()) out.push(`<p>${inline(line)}</p>`);
            i++;
        }
        return `<div class="md">${out.join("")}</div>`;
    }

    // Modal de justificativa/confirmação
    function govPrompt({ title, text, required = false, input = true, okLabel = "Confirmar" }) {
        return new Promise((resolve) => {
            const modal = $("govPromptModal");
            $("govPromptTitle").textContent = title;
            $("govPromptText").textContent = text || "";
            const field = $("govPromptInput");
            field.value = "";
            field.hidden = !input;
            $("govPromptOk").textContent = okLabel;
            modal.classList.add("open");
            if (input) setTimeout(() => field.focus(), 30);
            const done = (value) => {
                modal.classList.remove("open");
                $("govPromptOk").onclick = $("govPromptCancel").onclick = null;
                resolve(value);
            };
            $("govPromptCancel").onclick = () => done(null);
            $("govPromptOk").onclick = () => {
                const v = field.value.trim();
                if (input && required && !v) {
                    field.focus();
                    showToast("Preencha a justificativa.");
                    return;
                }
                done(input ? v : true);
            };
        });
    }

    // ------------------------------------------------------------------
    // Autenticação (opcional)
    // ------------------------------------------------------------------
    async function refreshAuth() {
        try {
            const me = await api("GET", "/api/auth/me");
            OntoGov.auth = { user: me.user, permissions: me.permissions || [] };
        } catch (_) {
            OntoGov.auth = { user: null, permissions: [] };
        }
        renderAuthArea();
    }

    function renderAuthArea() {
        const area = $("authArea");
        const user = OntoGov.auth.user;
        if (user) {
            area.innerHTML = `
              <span class="auth-chip" title="${esc(user.display_name)} — ${esc(user.role_label)}">👤
                <span class="auth-name">${esc(user.display_name)}</span>
                <span class="auth-role">${esc(user.role_label)}</span></span>
              <button class="btn btn-sm" id="btnLogout">↩ Sair</button>`;
            $("btnLogout").onclick = logout;
        } else {
            area.innerHTML = `<button class="btn btn-primary" id="btnLogin">🔐 Entrar</button>`;
            $("btnLogin").onclick = openAuthModal;
        }
        $("visitorBanner").hidden = !!user;
        renderContextBar();
        if ($("govModal").classList.contains("open")) renderGov();
    }

    function openAuthModal(tab = "login") {
        switchAuthTab(typeof tab === "string" ? tab : "login");
        $("authError").hidden = true;
        $("authModal").classList.add("open");
        setTimeout(() => $("loginUser").focus(), 30);
    }

    function switchAuthTab(tab) {
        document.querySelectorAll("[data-auth-tab]").forEach((b) => b.classList.toggle("active", b.dataset.authTab === tab));
        $("loginForm").hidden = tab !== "login";
        $("registerForm").hidden = tab !== "register";
    }

    function showAuthError(msg) {
        $("authError").textContent = msg;
        $("authError").hidden = false;
    }

    async function afterLogin(me) {
        OntoGov.auth = { user: me.user, permissions: me.permissions || [] };
        $("authModal").classList.remove("open");
        $("loginPass").value = "";
        $("regPass").value = "";
        renderAuthArea();
        showToast(`Bem-vindo(a), ${me.user.display_name} — ${me.user.role_label}.`);
    }

    async function logout() {
        try {
            await api("POST", "/api/auth/logout");
        } catch (_) { /* sessão já expirada */ }
        OntoGov.auth = { user: null, permissions: [] };
        exitContext(true);
        $("govModal").classList.remove("open");
        renderAuthArea();
        showToast("Você saiu. Modo visitante: as alterações deixam de ser salvas.");
    }

    // ------------------------------------------------------------------
    // Contexto do editor (proposta ou versão aberta)
    // ------------------------------------------------------------------
    function renderContextBar() {
        const bar = $("govContextBar");
        const ctx = OntoGov.context;
        if (!ctx || !OntoGov.auth.user) {
            bar.hidden = true;
            bar.innerHTML = "";
            return;
        }
        bar.hidden = false;
        if (ctx.kind === "version") {
            bar.innerHTML = `
              <span>📖 <strong>${esc(ctx.ontologyName)} v${esc(ctx.version)}</strong> — versão publicada (somente consulta;
                alterações aqui não são salvas)</span>
              <button class="btn btn-sm" data-ctx="exit">✕ Fechar contexto</button>`;
        } else {
            const buttons = [];
            if (ctx.canSave) {
                buttons.push(`<button class="btn btn-sm btn-primary" data-ctx="save">💾 ${ctx.role === "especialista" ? "Salvar correção" : "Salvar rascunho"}</button>`);
                if (ctx.role === "engenheiro") buttons.push(`<button class="btn btn-sm btn-emerald" data-ctx="submit">🛡️ Salvar e submeter</button>`);
            }
            if (ctx.candidates && ctx.candidates.length && ctx.canSave && ctx.role === "engenheiro") {
                buttons.push(`<button class="btn btn-sm btn-amber" data-ctx="candidates">🤖 Aplicar candidatos (${ctx.candidates.length})</button>`);
            }
            buttons.push(`<button class="btn btn-sm" data-ctx="open">📄 Proposta</button>`);
            buttons.push(`<button class="btn btn-sm" data-ctx="exit">✕</button>`);
            bar.innerHTML = `
              <span>📌 <strong>Proposta #${ctx.proposalId}</strong> — ${esc(ctx.title)} ·
                ${esc(ctx.ontologyName)} (base v${esc(ctx.baseVersion)}) · ${statusChip(ctx.status)}
                ${ctx.canSave ? "" : `<em class="ctx-ro">revisão: alterações não serão salvas</em>`}</span>
              <span class="ctx-actions">${buttons.join("")}</span>`;
        }
        bar.querySelectorAll("[data-ctx]").forEach((b) => {
            b.onclick = () => {
                const a = b.dataset.ctx;
                if (a === "save") saveWorkingCopy(false);
                else if (a === "submit") saveWorkingCopy(true);
                else if (a === "candidates") applyCandidatesToEditor(ctx.candidates);
                else if (a === "open") openGov("solicitacoes", { proposalId: ctx.proposalId });
                else if (a === "exit") exitContext();
            };
        });
    }

    function exitContext(silent) {
        if (!OntoGov.context) return;
        const ctx = OntoGov.context;
        OntoGov.context = null;
        OntoGov.loadedExport = null;
        renderContextBar();
        if (!silent) {
            showToast(ctx.kind === "proposal"
                ? `Você saiu do contexto da proposta #${ctx.proposalId}. O editor continua com o conteúdo, mas sem salvar.`
                : "Contexto fechado.");
        }
    }

    OntoGov.onLocalLoad = function (label) {
        if (OntoGov.context) {
            const id = OntoGov.context.proposalId;
            OntoGov.context = null;
            OntoGov.loadedExport = null;
            renderContextBar();
            showToast(id ? `"${label}" carregado localmente: saiu do contexto da proposta #${id}.` : `"${label}" carregado localmente.`);
        }
        if (!OntoGov.auth.user) {
            showToast("Modo visitante: o arquivo foi aberto só neste navegador e não será salvo.");
        }
    };

    function loadIntoEditor(contents) {
        // contents: [{ text, label }] — o primeiro vira v1, os seguintes v2..., com diff entre eles
        initEmptyOntology();
        contents.forEach((c) => parseOWLRDF(c.text, c.label));
        showAllOntologyOnStage();
    }

    async function openVersionInEditor(ontology, version) {
        const text = await api("GET", `/api/ontologies/${ontology.id}/versions/${encodeURIComponent(version)}?format=raw`);
        loadIntoEditor([{ text, label: `${ontology.name} v${version}` }]);
        OntoGov.context = { kind: "version", ontologyId: ontology.id, ontologyName: ontology.name, version };
        OntoGov.loadedExport = null;
        closeGov();
        renderContextBar();
        showToast(`${ontology.name} v${version} aberta no editor.`);
    }

    async function openProposalInEditor(p) {
        const user = OntoGov.auth.user;
        const base = await api("GET", `/api/proposals/${p.id}/working-copy?which=base`);
        const contents = [{ text: base, label: `Base v${p.base_version}` }];
        if (p.has_working_copy) {
            const working = await api("GET", `/api/proposals/${p.id}/working-copy?which=working`);
            contents.push({ text: working, label: `Cópia de trabalho #${p.id}` });
        }
        loadIntoEditor(contents);
        const canSave = !!(p.actions && p.actions.salvar_copia && p.actions.salvar_copia.allowed);
        OntoGov.context = {
            kind: "proposal",
            proposalId: p.id,
            title: p.title,
            ontologyId: p.ontology_id,
            ontologyName: p.ontology_name,
            baseVersion: p.base_version,
            status: p.status,
            role: user.role,
            canSave,
            candidates: p.candidates || []
        };
        OntoGov.loadedExport = serializeToOWLRDF();
        closeGov();
        renderContextBar();
        showToast(canSave
            ? `Cópia de trabalho da proposta #${p.id} aberta. Edite e use "Salvar" na faixa do palco.`
            : `Proposta #${p.id} aberta para revisão (diff base × cópia de trabalho).`);
    }

    async function saveWorkingCopy(submit) {
        const ctx = OntoGov.context;
        if (!ctx || ctx.kind !== "proposal") return;
        if (!OntoGov.auth.user) {
            openAuthModal();
            return;
        }
        const newExport = serializeToOWLRDF();
        try {
            showToast(submit ? "Salvando e executando a verificação automática (raciocinador + FAIR)..." : "Salvando cópia de trabalho...");
            const p = await api("POST", `/api/proposals/${ctx.proposalId}/working-copy`, {
                base_export: OntoGov.loadedExport,
                new_export: newExport,
                submit
            });
            OntoGov.loadedExport = newExport;
            ctx.status = p.status;
            ctx.canSave = !!(p.actions && p.actions.salvar_copia && p.actions.salvar_copia.allowed);
            renderContextBar();
            if (p.status === "inconsistente") {
                showToast("Verificação reprovou a proposta: veja os problemas no relatório.");
                openGov("solicitacoes", { proposalId: p.id });
            } else if (p.status === "em_validacao") {
                showToast(submit || ctx.role === "especialista"
                    ? "Consistente e com metadados FAIR: proposta em validação."
                    : "Cópia salva.");
                if (submit) openGov("solicitacoes", { proposalId: p.id });
            } else {
                showToast("Cópia de trabalho salva (commit no branch da proposta).");
            }
        } catch (err) {
            showToast("Não foi possível salvar: " + err.message);
        }
    }

    function applyCandidatesToEditor(candidates) {
        if (!candidates || !candidates.length) return;
        ensureOwlThing();
        const mkClass = (id, extra = {}) => {
            if (!ontology.classes.has(id)) {
                ontology.classes.set(id, {
                    id, iri: "", label: id, comment: "", source: "", creator: "",
                    parents: new Set(["owl:Thing"]), disjointWith: new Set(),
                    color: pickColor(ontology.classes.size), expanded: true, hidden: false,
                    x: 0, y: 0, z: 0, cellW: 215, cellD: 100
                });
            }
            Object.assign(ontology.classes.get(id), extra);
            return ontology.classes.get(id);
        };
        const fair = (c) => ({
            label: c.label || c.name,
            comment: (c.fair && c.fair["rdfs:comment"]) || c.definition || "",
            source: (c.fair && c.fair["dcterms:source"]) || "",
            creator: (c.fair && c.fair["dcterms:creator"]) || "Agente LLM (OntoCube)"
        });
        let n = 0;
        for (const c of candidates.filter((x) => x.kind === "class")) {
            mkClass(c.name, fair(c));
            n++;
        }
        for (const c of candidates.filter((x) => x.kind === "class")) {
            const cls = ontology.classes.get(c.name);
            if (c.parent && c.parent !== "owl:Thing") {
                mkClass(c.parent);
                cls.parents = new Set([c.parent]);
                ontology.classes.get(c.parent).expanded = true;
            }
        }
        for (const c of candidates.filter((x) => x.kind === "object_property")) {
            mkClass(c.domain);
            mkClass(c.range);
            ontology.objProps.set(c.name, {
                id: c.name, iri: "", ...fair(c), domain: c.domain, range: c.range, inverseOf: "",
                functional: false, symmetric: false, transitive: false, irreflexive: false, asymmetric: false
            });
            n++;
        }
        for (const c of candidates.filter((x) => x.kind === "datatype_property")) {
            mkClass(c.domain);
            ontology.dataProps.set(c.name, {
                id: c.name, iri: "", ...fair(c), domain: c.domain, range: c.datatype || "xsd:string", functional: false
            });
            n++;
        }
        createVersionSnapshot(`Candidatos do Agente LLM (${n})`);
        refreshAllUI();
        showAllOntologyOnStage();
        showToast(`${n} candidato(s) aplicados no editor. Revise, ajuste e salve a cópia de trabalho.`);
    }

    // ------------------------------------------------------------------
    // Painel de governança
    // ------------------------------------------------------------------
    function openGov(tab, view) {
        if (tab) state.tab = tab;
        state.view = view || null;
        $("govModal").classList.add("open");
        renderGov();
    }

    function closeGov() {
        $("govModal").classList.remove("open");
    }

    async function ensureMeta() {
        if (!OntoGov.meta) OntoGov.meta = await api("GET", "/api/governance/meta");
        return OntoGov.meta;
    }

    async function loadOntologies() {
        state.ontologies = await api("GET", "/api/ontologies");
        return state.ontologies;
    }

    function ontologyOptions(selected, includeAll) {
        return (includeAll ? `<option value="">Todas as ontologias</option>` : "") +
            state.ontologies.map((o) => `<option value="${o.id}" ${String(selected) === String(o.id) ? "selected" : ""}>${esc(o.name)} (v${esc(o.current_version)})</option>`).join("");
    }

    async function renderGov() {
        const body = $("govBody");
        document.querySelectorAll("[data-gov-tab]").forEach((b) => b.classList.toggle("active", b.dataset.govTab === state.tab));
        const user = OntoGov.auth.user;
        $("govSubtitle").textContent = user
            ? `${user.display_name} — ${user.role_label}`
            : "Modo visitante";
        // O painel cobre a barra superior: oferece "Sair" aqui também
        $("btnGovLogout").hidden = !user;
        try {
            await ensureMeta();
        } catch (err) {
            body.innerHTML = `<div class="gov-error">${esc(err.message)}</div>`;
            return;
        }
        if (!user && state.tab !== "papeis") {
            body.innerHTML = `
              <div class="gov-empty">
                <h3>Entre para acessar a governança</h3>
                <p>Sem login você usa o editor 3D livremente (criar, editar, explorar), mas nada é salvo e um F5 apaga tudo.
                   Com login, cada papel do modelo de governança tem suas permissões: Engenheiro de Conhecimento,
                   Especialista de Domínio e Stakeholder.</p>
                <button class="btn btn-primary" id="govLoginBtn">🔐 Entrar</button>
              </div>`;
            $("govLoginBtn").onclick = () => openAuthModal();
            return;
        }
        body.innerHTML = `<div class="gov-loading">Carregando…</div>`;
        try {
            if (state.tab !== "papeis") await loadOntologies();
            const renderers = {
                ontologias: renderOntologiesTab,
                solicitacoes: renderProposalsTab,
                validacao: renderValidationTab,
                historico: renderHistoryTab,
                agente: renderAgentTab,
                procedimentos: renderSopTab,
                papeis: renderRolesTab
            };
            await renderers[state.tab](body);
        } catch (err) {
            body.innerHTML = `<div class="gov-error">${esc(err.message)}</div>`;
        }
    }

    // ---------- Aba: Ontologias ----------
    async function renderOntologiesTab(body) {
        const v = state.view;
        if (v && v.versionsOf) return renderVersions(body, v.versionsOf);
        if (v && v.gitOf) return renderGitLog(body, v.gitOf);
        if (v && v.doc) return renderVersionDoc(body, v.doc.ontology, v.doc.version);

        const cards = state.ontologies.map((o) => `
          <div class="gov-card">
            <div class="gov-card-head">
              <div><strong>${esc(o.name)}</strong> <span class="badge-pill">v${esc(o.current_version)}</span></div>
              <span class="gov-muted">${esc(o.license)}</span>
            </div>
            <div class="gov-muted mono">${esc(o.iri)}</div>
            ${o.description ? `<p>${esc(o.description)}</p>` : ""}
            <div class="gov-muted">${o.open_proposals} proposta(s) em aberto · cadastrada por ${esc(o.created_by_name || "—")} em ${fmtDate(o.created_at)}</div>
            <div class="form-row wrap">
              <button class="btn btn-sm btn-primary" data-open-onto="${o.id}">🌐 Abrir versão atual no editor</button>
              <button class="btn btn-sm" data-versions="${o.id}">🕒 Versões</button>
              <button class="btn btn-sm" data-git="${o.id}">🌿 Histórico Git</button>
              <button class="btn btn-sm" data-new-prop="${o.id}">📝 Solicitar alteração</button>
            </div>
          </div>`).join("");

        body.innerHTML = `
          <div class="gov-toolbar">
            <span class="gov-muted">${state.ontologies.length} ontologia(s) governada(s)</span>
            ${can("cadastrar_ontologia") ? `<button class="btn btn-sm btn-emerald" id="btnShowRegister">➕ Cadastrar ontologia</button>` : ""}
          </div>
          <div id="registerBox" hidden></div>
          ${cards || `<div class="gov-empty"><p>Nenhuma ontologia cadastrada ainda.${can("cadastrar_ontologia") ? " Cadastre a primeira a partir do editor ou de um arquivo .owl." : ""}</p></div>`}`;

        const reg = $("btnShowRegister");
        if (reg) reg.onclick = () => showRegisterForm($("registerBox"));
        body.querySelectorAll("[data-open-onto]").forEach((b) => (b.onclick = async () => {
            const o = state.ontologies.find((x) => String(x.id) === b.dataset.openOnto);
            try { await openVersionInEditor(o, o.current_version); } catch (e) { showToast(e.message); }
        }));
        body.querySelectorAll("[data-versions]").forEach((b) => (b.onclick = () => { state.view = { versionsOf: +b.dataset.versions }; renderGov(); }));
        body.querySelectorAll("[data-git]").forEach((b) => (b.onclick = () => { state.view = { gitOf: +b.dataset.git }; renderGov(); }));
        body.querySelectorAll("[data-new-prop]").forEach((b) => (b.onclick = () => openGov("solicitacoes", { newProposal: +b.dataset.newProp })));
    }

    function showRegisterForm(box) {
        box.hidden = false;
        const editorHasContent = ontology.classes.size > 1 || ontology.objProps.size > 0;
        box.innerHTML = `
          <div class="gov-card">
            <div class="gov-card-head"><strong>Cadastrar ontologia (versão inicial 1.0.0)</strong></div>
            <div class="gov-grid">
              <label>Nome<input class="input" id="regOntoName" placeholder="Ex.: Ontologia do RADIAR" /></label>
              <label>IRI<input class="input" id="regOntoIri" placeholder="http://exemplo.org/minha-ontologia (vazio: usa o owl:Ontology do conteúdo)" /></label>
              <label class="span2">Descrição<input class="input" id="regOntoDesc" /></label>
              <label>Licença (dcterms:license)
                <select class="select" id="regOntoLicense">
                  ${Object.entries(OntoGov.meta.licenses).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}
                </select></label>
              <label>Conteúdo inicial
                <select class="select" id="regOntoSource">
                  <option value="editor" ${editorHasContent ? "selected" : ""}>Ontologia atual do editor</option>
                  <option value="file">Arquivo .owl/.rdf</option>
                  <option value="empty" ${editorHasContent ? "" : "selected"}>Vazia</option>
                </select></label>
              <label class="span2" id="regOntoFileWrap" hidden>Arquivo<input type="file" class="input" id="regOntoFile" accept=".owl,.rdf,.xml,.rdfs" /></label>
            </div>
            <p class="gov-hint">O cadastro cria o repositório Git da ontologia (branch main + tag v1.0.0), preenche os metadados
              obrigatórios (versionInfo, versionIRI, license) e executa o raciocinador na linha de base.</p>
            <div class="form-row"><button class="btn btn-emerald btn-sm" id="btnRegisterOnto">Cadastrar</button>
              <button class="btn btn-sm" id="btnCancelRegister">Cancelar</button></div>
          </div>`;
        $("regOntoSource").onchange = (e) => ($("regOntoFileWrap").hidden = e.target.value !== "file");
        $("regOntoFileWrap").hidden = $("regOntoSource").value !== "file";
        $("btnCancelRegister").onclick = () => { box.hidden = true; };
        $("btnRegisterOnto").onclick = async () => {
            const src = $("regOntoSource").value;
            let content = null;
            if (src === "editor") content = serializeToOWLRDF();
            if (src === "file") {
                const f = $("regOntoFile").files[0];
                if (!f) return showToast("Escolha o arquivo.");
                content = await f.text();
            }
            const btn = $("btnRegisterOnto");
            btn.disabled = true;
            btn.textContent = "Cadastrando (raciocinador em execução)…";
            try {
                const o = await api("POST", "/api/ontologies", {
                    name: $("regOntoName").value, iri: $("regOntoIri").value, description: $("regOntoDesc").value,
                    license: $("regOntoLicense").value, content
                });
                showToast(`Ontologia "${o.name}" cadastrada (v${o.current_version}; raciocinador: ${o.reasoner.status}).`);
                renderGov();
            } catch (e) {
                showToast(e.message);
                btn.disabled = false;
                btn.textContent = "Cadastrar";
            }
        };
    }

    async function renderVersions(body, ontologyId) {
        const o = await api("GET", `/api/ontologies/${ontologyId}`);
        body.innerHTML = `
          <div class="gov-toolbar"><button class="btn btn-sm" id="govBack">← Ontologias</button>
            <strong>${esc(o.name)} — versões publicadas</strong></div>
          <div class="table-scroll"><table class="gov-table">
            <thead><tr><th>Versão</th><th>Anterior</th><th>Mudança</th><th>Publicada</th><th>Publicador</th><th>Aprovador</th><th>Proposta</th><th>Raciocinador</th><th></th></tr></thead>
            <tbody>${o.versions.map((v) => `
              <tr>
                <td><strong>${esc(v.version)}</strong> <span class="gov-muted mono">${esc(v.git_tag || "")}</span></td>
                <td>${esc(v.prior_version || "—")}</td>
                <td><span class="impact impact-${esc(v.impact)}">${esc(v.impact)}</span></td>
                <td>${fmtDate(v.published_at)}</td>
                <td>${esc(v.publisher || "—")}</td>
                <td>${esc(v.approver || "—")}</td>
                <td>${v.proposal_id ? `<a href="#" data-prop="${v.proposal_id}">#${v.proposal_id}</a>` : "—"}</td>
                <td>${esc(v.reasoner_status || "—")} · ${v.inferred_count} inf.</td>
                <td class="nowrap">
                  <button class="btn btn-sm" data-open-ver="${esc(v.version)}">🌐 Editor</button>
                  <button class="btn btn-sm" data-doc="${esc(v.version)}">📄 Doc</button>
                  <a class="btn btn-sm" href="/api/ontologies/${o.id}/versions/${encodeURIComponent(v.version)}?format=owl">⬇ .owl</a>
                </td>
              </tr>`).join("")}</tbody></table></div>`;
        $("govBack").onclick = () => { state.view = null; renderGov(); };
        body.querySelectorAll("[data-open-ver]").forEach((b) => (b.onclick = () => openVersionInEditor(o, b.dataset.openVer).catch((e) => showToast(e.message))));
        body.querySelectorAll("[data-doc]").forEach((b) => (b.onclick = () => { state.view = { doc: { ontology: o, version: b.dataset.doc } }; renderGov(); }));
        body.querySelectorAll("[data-prop]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); openGov("solicitacoes", { proposalId: +a.dataset.prop }); }));
    }

    async function renderVersionDoc(body, o, version) {
        const v = await api("GET", `/api/ontologies/${o.id}/versions/${encodeURIComponent(version)}`);
        body.innerHTML = `
          <div class="gov-toolbar"><button class="btn btn-sm" id="govBack">← Versões</button>
            <strong>Documentação — ${esc(o.name)} v${esc(version)}</strong></div>
          ${renderMarkdown(v.documentation || "_Sem documentação._")}
          ${v.inferred_count ? `<details class="gov-details"><summary>Inferências materializadas (${v.inferred_count})</summary>
            ${triplesTable(v.inferred)}</details>` : ""}`;
        $("govBack").onclick = () => { state.view = { versionsOf: o.id }; renderGov(); };
    }

    async function renderGitLog(body, ontologyId) {
        const o = state.ontologies.find((x) => x.id === ontologyId);
        const g = await api("GET", `/api/ontologies/${ontologyId}/git-log`);
        body.innerHTML = `
          <div class="gov-toolbar"><button class="btn btn-sm" id="govBack">← Ontologias</button>
            <strong>${esc(o ? o.name : "")} — repositório Git</strong>
            <span class="gov-muted">tags: ${g.tags.map((t) => `<code>${esc(t)}</code>`).join(" ") || "—"}</span></div>
          <div class="table-scroll"><table class="gov-table">
            <thead><tr><th>Commit</th><th>Mensagem</th><th>Autor</th><th>Data</th><th>Refs</th></tr></thead>
            <tbody>${g.log.map((c) => `<tr><td class="mono">${esc(c.sha.slice(0, 8))}</td><td>${esc(c.subject)}</td>
              <td>${esc(c.author)}</td><td>${fmtDate(c.date)}</td><td class="mono">${esc(c.refs)}</td></tr>`).join("")}</tbody>
          </table></div>`;
        $("govBack").onclick = () => { state.view = null; renderGov(); };
    }

    function triplesTable(triples) {
        if (!triples || !triples.length) return `<div class="gov-muted">—</div>`;
        return `<div class="table-scroll"><table class="gov-table mono small"><tbody>${triples.map((t) =>
            `<tr>${t.map((x) => `<td title="${esc(x)}">${shortIri(String(x).replace(/^<|>$/g, ""))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }

    // ---------- Aba: Solicitações ----------
    async function renderProposalsTab(body) {
        const v = state.view;
        if (v && v.proposalId) return renderProposalDetail(body, v.proposalId);
        if (v && v.newProposal !== undefined) return renderNewProposal(body, v.newProposal);
        return renderProposalList(body, {});
    }

    async function renderProposalList(body, opts) {
        const f = state.filters;
        const status = opts.status || f.status;
        const qs = new URLSearchParams();
        if (f.ontology) qs.set("ontology_id", f.ontology);
        if (status) qs.set("status", status);
        if (f.mine && !opts.status) qs.set("mine", "1");
        const rows = await api("GET", `/api/proposals?${qs}`);
        const statuses = OntoGov.meta.statuses;
        body.innerHTML = `
          ${opts.intro || ""}
          <div class="gov-toolbar">
            <select class="select" id="fOnto">${ontologyOptions(f.ontology, true)}</select>
            ${opts.status ? "" : `<select class="select" id="fStatus"><option value="">Todos os status</option>
              ${Object.entries(statuses).map(([k, l]) => `<option value="${k}" ${f.status === k ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
              <label class="gov-check"><input type="checkbox" id="fMine" ${f.mine ? "checked" : ""}/> Minhas</label>`}
            <span class="spacer"></span>
            ${can("solicitar_alteracao") && !opts.status ? `<button class="btn btn-sm btn-emerald" id="btnNewProposal">➕ Nova solicitação</button>` : ""}
          </div>
          ${rows.length ? `<div class="table-scroll"><table class="gov-table clickable">
            <thead><tr><th>#</th><th>Título</th><th>Ontologia</th><th>Status</th><th>Origem</th><th>Solicitante</th><th>Responsável</th><th>Verificação</th><th>Atualizada</th></tr></thead>
            <tbody>${rows.map((p) => `
              <tr data-pid="${p.id}">
                <td>${p.id}</td>
                <td>${esc(p.title)}${p.candidates_count ? ` <span class="badge-pill">🤖 ${p.candidates_count}</span>` : ""}</td>
                <td>${esc(p.ontology_name)}</td>
                <td>${statusChip(p.status)}</td>
                <td>${p.origin === "automatica" ? "🤖 automática" : "👤 humana"}</td>
                <td>${esc(p.requester_name)}</td>
                <td>${esc(p.assignee_name || "—")}</td>
                <td>${p.check_ok === true ? "✅" : p.check_ok === false ? "❌" : "—"}</td>
                <td>${fmtDate(p.updated_at)}</td>
              </tr>`).join("")}</tbody></table></div>`
            : `<div class="gov-empty"><p>Nenhuma solicitação encontrada.</p></div>`}`;
        $("fOnto").onchange = (e) => { f.ontology = e.target.value; renderGov(); };
        if ($("fStatus")) $("fStatus").onchange = (e) => { f.status = e.target.value; renderGov(); };
        if ($("fMine")) $("fMine").onchange = (e) => { f.mine = e.target.checked; renderGov(); };
        if ($("btnNewProposal")) $("btnNewProposal").onclick = () => { state.view = { newProposal: f.ontology || "" }; renderGov(); };
        body.querySelectorAll("[data-pid]").forEach((tr) => (tr.onclick = () => openGov("solicitacoes", { proposalId: +tr.dataset.pid })));
    }

    function renderNewProposal(body, ontologyId) {
        if (!state.ontologies.length) {
            body.innerHTML = `<div class="gov-empty"><p>Cadastre uma ontologia antes de abrir solicitações.</p></div>`;
            return;
        }
        body.innerHTML = `
          <div class="gov-toolbar"><button class="btn btn-sm" id="govBack">← Solicitações</button><strong>Nova solicitação de alteração</strong></div>
          <div class="gov-card">
            <div class="gov-grid">
              <label>Ontologia<select class="select" id="npOnto">${ontologyOptions(ontologyId, false)}</select></label>
              <label>Título<input class="input" id="npTitle" placeholder="Ex.: Incluir a classe Professor" /></label>
              <label class="span2">Descrição da necessidade *<textarea class="textarea" id="npDesc" rows="3"></textarea></label>
              <label class="span2">Justificativa *<textarea class="textarea" id="npJust" rows="3"></textarea></label>
              <label>Elementos afetados (separados por vírgula)<input class="input" id="npAffected" placeholder="Professor, leciona" /></label>
              <label>Fonte do conhecimento (dcterms:source)<input class="input" id="npSource" placeholder="Documento, norma ou URL" /></label>
              <label class="span2">Evidência<textarea class="textarea" id="npEvidence" rows="2"></textarea></label>
            </div>
            <p class="gov-hint">Solicitante, origem (humana) e data são registrados automaticamente. A solicitação entra como <strong>Pendente</strong>.</p>
            <div class="form-row"><button class="btn btn-emerald btn-sm" id="npSubmit">Registrar solicitação</button></div>
          </div>`;
        $("govBack").onclick = () => { state.view = null; renderGov(); };
        $("npSubmit").onclick = async () => {
            try {
                const p = await api("POST", "/api/proposals", {
                    ontology_id: +$("npOnto").value, title: $("npTitle").value, description: $("npDesc").value,
                    justification: $("npJust").value, affected_elements: $("npAffected").value,
                    source: $("npSource").value, evidence: $("npEvidence").value
                });
                showToast(`Solicitação #${p.id} registrada.`);
                openGov("solicitacoes", { proposalId: p.id });
            } catch (e) {
                showToast(e.message);
            }
        };
    }

    function reportHtml(p) {
        const r = p.check_report;
        if (!r) return `<div class="gov-muted">Ainda não verificada.</div>`;
        const rs = r.reasoner || {};
        const fair = r.fair || {};
        const stale = r.working_commit && p.working_commit && r.working_commit !== p.working_commit;
        return `
          <div class="report ${r.ok ? "report-ok" : "report-bad"}">
            <div><strong>${r.ok ? "✅ Aprovada na verificação automática" : "❌ Reprovada na verificação automática"}</strong>
              · impacto <span class="impact impact-${esc(r.impact)}">${esc(r.impact)}</span>
              · ${fmtDate(r.checked_at)}${stale ? ` · <em>a cópia mudou depois desta verificação</em>` : ""}</div>
            ${(r.problems || []).length ? `<ul>${r.problems.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
          </div>
          <div class="gov-two">
            <div class="gov-card">
              <div class="gov-card-head"><strong>Raciocinador</strong><span class="gov-muted">${esc(rs.reasoner || "")}</span></div>
              <div>Status: <strong>${esc(rs.status)}</strong> — ${esc(rs.message || "")} ${rs.duration_s ? `(${rs.duration_s}s)` : ""}</div>
              ${(rs.unsatisfiable || []).length ? `<div>Classes insatisfatíveis: ${rs.unsatisfiable.map((c) => `<code>${shortIri(c)}</code>`).join(", ")}</div>` : ""}
              <details class="gov-details"><summary>Inferências (${rs.inferred_count || 0})</summary>${triplesTable(rs.inferred)}</details>
            </div>
            <div class="gov-card">
              <div class="gov-card-head"><strong>Metadados FAIR</strong><span class="gov-muted">${esc((fair.required || []).join(", "))}</span></div>
              ${fair.ok ? `<div>✅ ${fair.checked} elemento(s) novo(s)/alterado(s) com metadados completos.</div>`
                : `<ul>${(fair.errors || []).map((e) => `<li><code>${shortIri(e.concept)}</code>: falta ${esc(e.missing.join(", "))}</li>`).join("")}</ul>`}
              ${fair.legacy_missing_count ? `<div class="gov-muted">Aviso: ${fair.legacy_missing_count} elemento(s) não alterados sem metadados completos.</div>` : ""}
            </div>
          </div>`;
    }

    function diffHtml(diff) {
        if (!diff || !diff.concepts) return "";
        return `
          <details class="gov-details" open><summary>Diff semântico em relação à base (${diff.concepts.length} conceito(s);
            +${diff.counts.triples_added} / -${diff.counts.triples_removed} triplas)</summary>
          <div class="table-scroll"><table class="gov-table">
            <thead><tr><th>Conceito</th><th>Mudança</th><th>Impacto</th><th>Motivos</th></tr></thead>
            <tbody>${diff.concepts.map((c) => `<tr><td title="${esc(c.concept)}"><code>${shortIri(c.concept)}</code></td>
              <td>${esc(c.change_type)}</td><td><span class="impact impact-${esc(c.impact)}">${esc(c.impact)}</span></td>
              <td>${esc(c.reasons.join("; "))}</td></tr>`).join("")}</tbody></table></div></details>`;
    }

    function candidatesHtml(cands) {
        if (!cands || !cands.length) return "";
        const kinds = { class: "Classe", object_property: "Relação", datatype_property: "Atributo" };
        return `
          <details class="gov-details" open><summary>🤖 Candidatos do Agente LLM (${cands.length})</summary>
          <div class="table-scroll"><table class="gov-table">
            <thead><tr><th>Tipo</th><th>Nome</th><th>Rótulo</th><th>Definição</th><th>Tripla</th><th>Evidência</th><th>Sim.</th></tr></thead>
            <tbody>${cands.map((c) => `<tr><td>${kinds[c.kind] || esc(c.kind)}</td><td><code>${esc(c.name)}</code></td>
              <td>${esc(c.label)}</td><td>${esc(c.definition)}</td><td class="mono small">${esc((c.triple || []).join(" · "))}</td>
              <td class="small">${esc(c.evidence)}</td><td>${c.similarity != null ? esc(c.similarity) : "—"}</td></tr>`).join("")}</tbody>
          </table></div></details>`;
    }

    async function renderProposalDetail(body, pid) {
        const p = await api("GET", `/api/proposals/${pid}`);
        const a = p.actions || {};
        const user = OntoGov.auth.user;
        const btn = (key, label, cls = "") => (a[key] && a[key].allowed ? `<button class="btn btn-sm ${cls}" data-act="${key}">${label}</button>` : "");
        const editable = a.salvar_copia && a.salvar_copia.allowed;
        const canOpen = p.base_version && p.status !== "pendente";
        const reopen = p.base_outdated && user.role === "engenheiro" && p.assignee_id === user.id && !["publicada", "rejeitada"].includes(p.status);

        body.innerHTML = `
          <div class="gov-toolbar"><button class="btn btn-sm" id="govBack">← Solicitações</button>
            <strong>#${p.id} — ${esc(p.title)}</strong> ${statusChip(p.status)}
            <span class="badge-pill">${p.origin === "automatica" ? "🤖 origem automática" : "👤 origem humana"}</span></div>
          ${p.base_outdated ? `<div class="gov-warn">⚠️ A versão base (${esc(p.base_version)}) ficou desatualizada: a oficial agora é ${esc(p.ontology_version)}.
             ${reopen ? "Use “Reabrir sobre a versão atual”." : "O Engenheiro responsável precisa reabrir a proposta sobre a versão atual."}</div>` : ""}
          <div class="gov-actions">
            ${btn("iniciar_analise", "▶ Iniciar análise", "btn-primary")}
            ${canOpen ? `<button class="btn btn-sm ${editable ? "btn-primary" : ""}" data-act="open">${editable ? "✏️ Abrir cópia de trabalho no editor" : "🔍 Revisar no editor (diff)"}</button>` : ""}
            ${btn("submeter", "🛡️ Submeter à verificação", "btn-emerald")}
            ${btn("aprovar", "✅ Aprovar", "btn-emerald")}
            ${btn("solicitar_ajustes", "↩ Solicitar ajustes", "btn-amber")}
            ${btn("rejeitar", "⛔ Rejeitar", "btn-rose")}
            ${btn("publicar", "🚀 Publicar nova versão", "btn-emerald")}
            ${reopen ? `<button class="btn btn-sm btn-amber" data-act="reabrir_base_atual">♻ Reabrir sobre a versão atual</button>` : ""}
          </div>
          ${blockedReasons(a, p.status)}
          <div class="gov-two">
            <div class="gov-card">
              <dl class="gov-dl">
                <dt>Ontologia</dt><dd>${esc(p.ontology_name)} (oficial v${esc(p.ontology_version)})</dd>
                <dt>Versão base</dt><dd>${esc(p.base_version || "— (definida ao iniciar a análise)")}</dd>
                <dt>Solicitante</dt><dd>${esc(p.requester_name)} · ${fmtDate(p.created_at)}</dd>
                <dt>Responsável</dt><dd>${esc(p.assignee_name || "—")}</dd>
                <dt>Branch Git</dt><dd class="mono">${esc(p.branch || "—")} ${p.working_commit ? `@ ${esc(p.working_commit.slice(0, 8))}` : ""}</dd>
                <dt>Elementos afetados</dt><dd>${(p.affected_elements || []).map((x) => `<code>${esc(x)}</code>`).join(" ") || "—"}</dd>
                <dt>Fonte</dt><dd>${esc(p.source || "—")}</dd>
                ${p.decided_by_name ? `<dt>Decisão</dt><dd>${esc(p.decided_by_name)} · ${fmtDate(p.decided_at)}${p.decision_reason ? ` — ${esc(p.decision_reason)}` : ""}</dd>` : ""}
                ${p.published_version ? `<dt>Publicada em</dt><dd>v${esc(p.published_version)}</dd>` : ""}
              </dl>
            </div>
            <div class="gov-card">
              <div class="gov-label">Descrição</div><p class="pre">${esc(p.description)}</p>
              <div class="gov-label">Justificativa</div><p class="pre">${esc(p.justification)}</p>
              ${p.evidence ? `<div class="gov-label">Evidência</div><p class="pre small">${esc(p.evidence)}</p>` : ""}
            </div>
          </div>
          ${candidatesHtml(p.candidates)}
          <h4 class="gov-h">Verificação automática</h4>
          ${reportHtml(p)}
          ${diffHtml(p.diff_summary)}
          <div class="gov-two">
            <div class="gov-card">
              <div class="gov-card-head"><strong>💬 Deliberação (${p.comments.length})</strong></div>
              ${p.comments.map((c) => `<div class="comment"><div class="gov-muted">${esc(c.author)} · ${esc((OntoGov.meta.roles || {})[c.author_role] || c.author_role)} · ${fmtDate(c.created_at)}</div><div class="pre">${esc(c.body)}</div></div>`).join("") || `<div class="gov-muted">Sem comentários.</div>`}
              ${a.comentar && a.comentar.allowed ? `<textarea class="textarea" id="commentText" rows="2" placeholder="Comentar…"></textarea>
                <div class="form-row"><button class="btn btn-sm" id="btnComment">Comentar</button></div>` : ""}
            </div>
            <div class="gov-card">
              <div class="gov-card-head"><strong>🧾 Histórico e auditoria</strong></div>
              <ol class="timeline">${p.events.map((e) => `<li><span class="gov-muted">${fmtDate(e.created_at)}</span>
                <strong>${esc(e.actor)}</strong> — ${esc(e.action)}${e.to_status && e.to_status !== e.from_status ? ` → ${statusChip(e.to_status)}` : ""}
                ${e.note ? `<div class="small pre">${esc(e.note)}</div>` : ""}</li>`).join("")}</ol>
            </div>
          </div>`;

        $("govBack").onclick = () => { state.view = null; renderGov(); };
        if ($("btnComment")) {
            $("btnComment").onclick = async () => {
                try {
                    await api("POST", `/api/proposals/${p.id}/comments`, { body: $("commentText").value });
                    renderGov();
                } catch (e) { showToast(e.message); }
            };
        }
        body.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => runAction(p, b.dataset.act, b)));
    }

    function blockedReasons(actions, status) {
        // Explica por que a ação principal da etapa atual não está disponível para este usuário
        const stageAction = { em_validacao: "aprovar", aprovada: "publicar", em_analise: "submeter",
            inconsistente: "submeter", aguardando_ajustes: "submeter" }[status];
        const keys = stageAction ? [stageAction] : [];
        const msgs = keys
            .filter((k) => actions[k] && !actions[k].allowed && actions[k].reason && !/papel/.test(actions[k].reason))
            .map((k) => `<li><strong>${esc(actions[k].label)}:</strong> ${esc(actions[k].reason)}</li>`);
        return msgs.length ? `<ul class="gov-blocked">${msgs.join("")}</ul>` : "";
    }

    async function runAction(p, action, button) {
        try {
            if (action === "open") return await openProposalInEditor(p);
            let payload;
            if (action === "rejeitar" || action === "solicitar_ajustes") {
                const reason = await govPrompt({
                    title: action === "rejeitar" ? `Rejeitar a proposta #${p.id}` : `Solicitar ajustes na proposta #${p.id}`,
                    text: action === "rejeitar" ? "Justificativa (fica registrada no histórico):" : "O que precisa ser ajustado:",
                    required: true
                });
                if (reason === null) return;
                payload = { reason };
            }
            if (action === "aprovar") {
                const ok = await govPrompt({ title: `Aprovar a proposta #${p.id}`, text: "Comentário opcional da aprovação:", okLabel: "Aprovar" });
                if (ok === null) return;
                payload = { reason: ok };
            }
            if (action === "publicar") {
                const ok = await govPrompt({
                    title: `Publicar a proposta #${p.id}`, input: false, okLabel: "Publicar",
                    text: `Será gerada uma nova versão de ${p.ontology_name} (impacto ${p.impact || "?"}), com tag Git, documentação e registro no Version Log.`
                });
                if (!ok) return;
            }
            button.disabled = true;
            if (action === "submeter") showToast("Executando raciocinador e checagem FAIR…");
            const res = await api("POST", `/api/proposals/${p.id}/actions/${action}`, payload || {});
            if (action === "publicar") showToast(`Publicada a versão ${res.version} (${res.impact}) — tag ${res.tag}.`);
            else showToast(`Proposta #${p.id}: ${(OntoGov.meta.statuses[(res.status || (res.proposal || {}).status)] || "atualizada")}.`);
            if (OntoGov.context && OntoGov.context.proposalId === p.id) {
                OntoGov.context.status = res.status || (res.proposal || {}).status;
                renderContextBar();
            }
            renderGov();
        } catch (e) {
            showToast(e.message);
            if (button) button.disabled = false;
        }
    }

    // ---------- Aba: Validação ----------
    async function renderValidationTab(body) {
        if (state.view && state.view.proposalId) return renderProposalDetail(body, state.view.proposalId);
        const isSpecialist = OntoGov.auth.user.role === "especialista";
        return renderProposalList(body, {
            status: "em_validacao",
            intro: `<p class="gov-hint">${isSpecialist
                ? "Propostas consistentes aguardando sua validação. Abra uma proposta para ver o relatório do raciocinador, o diff e decidir (aprovar, rejeitar ou solicitar ajustes)."
                : "Propostas consistentes aguardando o Especialista de Domínio. Stakeholders podem contribuir comentando."}</p>`
        });
    }

    // ---------- Aba: Version Log / CDL ----------
    async function renderHistoryTab(body) {
        const oid = state.cdlOntology || (state.ontologies[0] && state.ontologies[0].id);
        if (!oid) {
            body.innerHTML = `<div class="gov-empty"><p>Nenhuma ontologia cadastrada.</p></div>`;
            return;
        }
        state.cdlOntology = oid;
        const examples = ["VERSIONS", "CHANGES", "CHANGES WHERE impact=major", "CHANGES WHERE kind=inferred",
            "HISTORY Pessoa", "WHO CHANGED Pessoa", "STATE Pessoa AT 1.0.0", "CHANGES FROM 1.0.0 TO 2.0.0"];
        body.innerHTML = `
          <div class="gov-toolbar">
            <select class="select" id="cdlOnto">${ontologyOptions(oid, false)}</select>
            <input class="input mono grow" id="cdlQuery" value="${esc(state.cdlQuery || "CHANGES")}" />
            <button class="btn btn-sm btn-primary" id="cdlRun">Executar CDL</button>
          </div>
          <div class="chip-list">${examples.map((q) => `<span class="chip" data-q="${esc(q)}">${esc(q)}</span>`).join("")}</div>
          <p class="gov-hint">CDL (Change Definition Language): consultas temporais sobre o Version Log — alterações declaradas e
            inferências materializadas, por conceito e por versão. Veja WIN-04 em Procedimentos.</p>
          <div id="cdlResult"></div>`;
        const run = async () => {
            state.cdlQuery = $("cdlQuery").value;
            state.cdlOntology = +$("cdlOnto").value;
            const out = $("cdlResult");
            try {
                const res = await api("POST", `/api/ontologies/${state.cdlOntology}/cdl`, { query: state.cdlQuery });
                out.innerHTML = (res.description ? `<p class="gov-hint">${esc(res.description)}</p>` : "") + cdlTable(res);
            } catch (e) {
                out.innerHTML = `<div class="gov-error">${esc(e.message)}</div>`;
            }
        };
        $("cdlRun").onclick = run;
        $("cdlQuery").onkeydown = (e) => { if (e.key === "Enter") run(); };
        $("cdlOnto").onchange = run;
        body.querySelectorAll("[data-q]").forEach((c) => (c.onclick = () => { $("cdlQuery").value = c.dataset.q; run(); }));
        run();
    }

    function cdlTable(res) {
        if (!res.rows.length) return `<div class="gov-muted">Nenhum resultado.</div>`;
        const cell = (col, v) => {
            if (Array.isArray(v)) {
                return v.length ? `<details><summary>${v.length} tripla(s)</summary>${triplesTable(v)}</details>` : "—";
            }
            if (col === "concept_iri" || col === "subject" || col === "object" || col === "predicate") {
                return `<span title="${esc(v)}" class="mono">${shortIri(String(v).replace(/^<|>$/g, ""))}</span>`;
            }
            if (col === "impact" && v) return `<span class="impact impact-${esc(v)}">${esc(v)}</span>`;
            if (/_at$/.test(col)) return fmtDate(v);
            return v == null || v === "" ? "—" : esc(v);
        };
        return `<div class="gov-muted">${res.rows.length} linha(s)</div>
          <div class="table-scroll"><table class="gov-table"><thead><tr>${res.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
          <tbody>${res.rows.map((r) => `<tr>${res.columns.map((c) => `<td>${cell(c, r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }

    // ---------- Aba: Agente LLM ----------
    async function renderAgentTab(body) {
        const enabled = OntoGov.meta.agent_enabled;
        const allowed = can("executar_agente");
        body.innerHTML = `
          <p class="gov-hint">Pipeline de Ontology Learning: o agente (Claude) lê o texto do domínio, propõe classes, relações e
            atributos com definição e evidência, descarta duplicatas por <strong>similaridade vetorial</strong>, anexa as anotações
            FAIR e <strong>abre automaticamente uma solicitação</strong>. Ele nunca altera a versão oficial (SOP-02).</p>
          ${!enabled ? `<div class="gov-warn">Agente desativado: defina <code>ANTHROPIC_API_KEY</code> no arquivo <code>.env</code> e reinicie o container.</div>` : ""}
          ${!allowed ? `<div class="gov-warn">Só o Engenheiro de Conhecimento dispara a ingestão do agente.</div>` : ""}
          <div class="gov-card">
            <div class="gov-grid">
              <label>Ontologia<select class="select" id="agOnto">${ontologyOptions(state.cdlOntology, false)}</select></label>
              <label>Fonte (dcterms:source)<input class="input" id="agSource" placeholder="Ex.: Regimento interno, 2026" /></label>
              <label class="span2">Texto do domínio
                <textarea class="textarea" id="agText" rows="8" placeholder="Cole aqui o trecho do documento…"></textarea></label>
              <label>Ou carregar arquivo de texto<input type="file" class="input" id="agFile" accept=".txt,.md,.csv" /></label>
              <label>Máximo de candidatos<input type="number" class="input" id="agMax" value="15" min="1" max="60" /></label>
            </div>
            <div class="form-row"><button class="btn btn-emerald btn-sm" id="agRun" ${enabled && allowed && state.ontologies.length ? "" : "disabled"}>🤖 Executar agente</button></div>
          </div>
          <div id="agResult"></div>`;
        $("agFile").onchange = async (e) => {
            const f = e.target.files[0];
            if (!f) return;
            $("agText").value = await f.text();
            if (!$("agSource").value) $("agSource").value = f.name;
        };
        $("agRun").onclick = async () => {
            const btn = $("agRun");
            btn.disabled = true;
            btn.textContent = "Gerando candidatos…";
            const out = $("agResult");
            try {
                const res = await api("POST", "/api/agent/run", {
                    ontology_id: +$("agOnto").value, source: $("agSource").value, text: $("agText").value,
                    max_candidates: +$("agMax").value || 15
                });
                out.innerHTML = `
                  ${res.proposal ? `<div class="report report-ok">Solicitação <a href="#" data-prop="${res.proposal.id}">#${res.proposal.id}</a> aberta automaticamente
                    com ${res.candidates.length} candidato(s). Modelo: ${esc(res.model)}.</div>`
                    : `<div class="gov-warn">Nenhum candidato novo depois da filtragem.</div>`}
                  ${candidatesHtml(res.candidates)}
                  ${res.filtered_out.length ? `<details class="gov-details"><summary>Descartados pela filtragem vetorial (${res.filtered_out.length})</summary>
                    <ul>${res.filtered_out.map((c) => `<li><code>${esc(c.name)}</code> — ${esc(c.reason)} (similaridade ${esc(c.similarity)})</li>`).join("")}</ul></details>` : ""}`;
                out.querySelectorAll("[data-prop]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); openGov("solicitacoes", { proposalId: +a.dataset.prop }); }));
            } catch (e) {
                out.innerHTML = `<div class="gov-error">${esc(e.message)}</div>`;
            } finally {
                btn.disabled = false;
                btn.textContent = "🤖 Executar agente";
            }
        };
    }

    // ---------- Aba: Procedimentos (SOP/WIN) ----------
    async function renderSopTab(body) {
        const docs = await api("GET", "/api/governance/sops");
        const current = state.sop || (docs[0] && docs[0].id);
        body.innerHTML = `
          <div class="gov-split">
            <ul class="gov-nav">${docs.map((d) => `<li class="${d.id === current ? "active" : ""}" data-sop="${esc(d.id)}">${esc(d.title)}</li>`).join("")}</ul>
            <div id="sopContent" class="gov-doc"></div>
          </div>`;
        body.querySelectorAll("[data-sop]").forEach((li) => (li.onclick = () => { state.sop = li.dataset.sop; renderGov(); }));
        if (current) {
            const doc = await api("GET", `/api/governance/sops/${encodeURIComponent(current)}`);
            $("sopContent").innerHTML = renderMarkdown(doc.content);
        }
    }

    // ---------- Aba: Papéis e acesso ----------
    function renderRolesTab(body) {
        const meta = OntoGov.meta;
        const roles = ["engenheiro", "especialista", "stakeholder", "agente"];
        const labels = {
            consultar_ontologia: "Consultar ontologia", consultar_historico: "Consultar histórico (Version Log)",
            solicitar_alteracao: "Solicitar alterações", comentar: "Comentar / deliberar propostas",
            gerar_candidatos: "Gerar candidatos automaticamente", executar_agente: "Disparar ingestão do Agente LLM",
            cadastrar_ontologia: "Cadastrar ontologias", analisar_proposta: "Assumir/analisar solicitação",
            editar_ontologia: "Criar/alterar classes, relações e triplas", corrigir_triplas: "Corrigir novas triplas",
            submeter_verificacao: "Submeter à verificação automática", validar_alteracao: "Validar / aprovar / rejeitar",
            publicar_versao: "Publicar nova versão"
        };
        const user = OntoGov.auth.user;
        body.innerHTML = `
          <p class="gov-hint">Matriz de permissões do modelo de governança (seção 2), aplicada no servidor em cada requisição.
            ${user ? `Seu papel: <strong>${esc(user.role_label)}</strong>.` : "Você está no modo visitante: pode usar o editor, mas nada é salvo."}</p>
          <div class="table-scroll"><table class="gov-table matrix">
            <thead><tr><th>Funcionalidade</th>${roles.map((r) => `<th>${esc(meta.roles[r])}</th>`).join("")}</tr></thead>
            <tbody>${Object.entries(meta.permissions).map(([perm, rs]) => `<tr><td>${esc(labels[perm] || perm)}</td>
              ${roles.map((r) => `<td class="${rs.includes(r) ? "yes" : "no"}">${rs.includes(r) ? "Sim" : "Não"}</td>`).join("")}</tr>`).join("")}</tbody>
          </table></div>
          <ul class="gov-hint">
            <li>Quem solicitou ou construiu a alteração não aprova a própria proposta.</li>
            <li>Nenhuma alteração gerada automaticamente é publicada sem validação humana.</li>
            <li>A publicação só é permitida para propostas com status <strong>Aprovada</strong>.</li>
            <li>Licença padrão das ontologias: <strong>CC BY 4.0</strong> (ou CC0), declarada em <code>dcterms:license</code>.</li>
          </ul>`;
    }

    // ------------------------------------------------------------------
    // Inicialização
    // ------------------------------------------------------------------
    function bind() {
        $("btnOpenGov").onclick = () => openGov(state.tab);
        $("btnCloseGov").onclick = closeGov;
        $("btnGovLogout").onclick = logout;
        $("btnCloseAuth").onclick = () => $("authModal").classList.remove("open");
        $("btnVisitorLogin").onclick = () => openAuthModal();
        document.querySelectorAll("[data-gov-tab]").forEach((b) => (b.onclick = () => openGov(b.dataset.govTab)));
        document.querySelectorAll("[data-auth-tab]").forEach((b) => (b.onclick = () => switchAuthTab(b.dataset.authTab)));

        $("loginForm").onsubmit = async (e) => {
            e.preventDefault();
            try {
                afterLogin(await api("POST", "/api/auth/login", { username: $("loginUser").value, password: $("loginPass").value }));
            } catch (err) {
                showAuthError(err.message);
            }
        };
        $("registerForm").onsubmit = async (e) => {
            e.preventDefault();
            try {
                afterLogin(await api("POST", "/api/auth/register", {
                    display_name: $("regName").value, username: $("regUser").value, password: $("regPass").value
                }));
            } catch (err) {
                showAuthError(err.message);
            }
        };
        document.addEventListener("keydown", (e) => {
            if (e.key !== "Escape") return;
            if ($("govPromptModal").classList.contains("open")) $("govPromptCancel").click();
            else if ($("authModal").classList.contains("open")) $("authModal").classList.remove("open");
            else if ($("govModal").classList.contains("open")) closeGov();
        });
    }

    window.addEventListener("DOMContentLoaded", () => {
        bind();
        renderAuthArea();
        refreshAuth();
    });
})();
