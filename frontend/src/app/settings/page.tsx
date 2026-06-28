"use client";

import { useEffect, useState } from "react";
import Layout from "@/components/layout/Layout";
import { useTranslations } from "next-intl";
import { Palette, Brain, Save, Monitor, Key, Globe, Zap, Cpu, Cloud, Loader2 } from "lucide-react";
import { getUserSettingsWithFallback, saveUserSettingsWithFallback, UserSettings } from "@/lib/api";

type Tab = "appearance" | "model";

interface SettingsState {
  theme: "dark" | "light";
  accentColor: string;
  modelType: "local" | "online";
  localLlmUrl: string;
  localLlmModel: string;
  localLlmTemperature: number;
  localLlmMaxTokens: number;
  onlineLlmProvider: string;
  onlineLlmApiKey: string;
  onlineLlmBaseUrl: string;
  onlineLlmModel: string;
  onlineLlmTemperature: number;
  onlineLlmMaxTokens: number;
}

const DEFAULTS: SettingsState = {
  theme: "dark",
  accentColor: "#6366f1",
  modelType: "online",
  localLlmUrl: "http://localhost:11434",
  localLlmModel: "",
  localLlmTemperature: 0.7,
  localLlmMaxTokens: 8192,
  onlineLlmProvider: "openai",
  onlineLlmApiKey: "",
  onlineLlmBaseUrl: "https://api.openai.com/v1",
  onlineLlmModel: "claude-sonnet-4-6",
  onlineLlmTemperature: 0.7,
  onlineLlmMaxTokens: 8192,
};

function fromApi(api: UserSettings): SettingsState {
  return {
    theme: api.theme || "dark",
    accentColor: api.accentColor || "#6366f1",
    modelType: api.modelType || "online",
    localLlmUrl: api.localLlm?.url || "",
    localLlmModel: api.localLlm?.model || "",
    localLlmTemperature: api.localLlm?.temperature ?? 0.7,
    localLlmMaxTokens: api.localLlm?.maxTokens ?? 8192,
    onlineLlmProvider: api.onlineLlm?.provider || "openai",
    onlineLlmApiKey: api.onlineLlm?.apiKey || "",
    onlineLlmBaseUrl: api.onlineLlm?.baseUrl || "https://api.openai.com/v1",
    onlineLlmModel: api.onlineLlm?.model || "claude-sonnet-4-6",
    onlineLlmTemperature: api.onlineLlm?.temperature ?? 0.7,
    onlineLlmMaxTokens: api.onlineLlm?.maxTokens ?? 8192,
  };
}

export default function SettingsPage() {
  const t = useTranslations("settings");
  const [activeTab, setActiveTab] = useState<Tab>("appearance");
  const [s, setS] = useState<SettingsState>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [savedLocally, setSavedLocally] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getUserSettingsWithFallback()
      .then((api) => {
        setS(fromApi(api));
      })
      .catch(() => {
        /* Should not reach here — fallback always returns something */
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSavedLocally(false);
    try {
      const ok = await saveUserSettingsWithFallback({
        modelType: s.modelType,
        theme: s.theme,
        accentColor: s.accentColor,
        localLlm: {
          url: s.localLlmUrl,
          model: s.localLlmModel,
          temperature: s.localLlmTemperature,
          maxTokens: s.localLlmMaxTokens,
        },
        onlineLlm: {
          provider: s.onlineLlmProvider,
          apiKey: s.onlineLlmApiKey,
          baseUrl: s.onlineLlmBaseUrl,
          model: s.onlineLlmModel,
          temperature: s.onlineLlmTemperature,
          maxTokens: s.onlineLlmMaxTokens,
        },
      });
      if (ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        setSavedLocally(true);
        setTimeout(() => setSavedLocally(false), 3000);
      }
    } catch (e: unknown) {
      setError((e as Error).message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const update = (key: string, val: string | number) => {
    setS((prev) => ({ ...prev, [key]: val }));
    setSaved(false);
    setSavedLocally(false);
  };

  const tabs: Array<{ key: Tab; icon: any; label: string }> = [
    { key: "appearance", icon: Palette, label: t("tabAppearance") },
    { key: "model", icon: Brain, label: t("tabModel") },
  ];

  const inputCls =
    "w-full px-3 py-2 bg-zinc-900 border border-border rounded-md text-sm focus:outline-none focus:border-brand-500";
  const labelCls = "block text-xs text-zinc-400 mb-1";
  const fieldCls = "mb-4";

  if (loading) {
    return (
      <Layout>
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="flex-1 overflow-auto">
        <div className="max-w-3xl mx-auto p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold">{t("title")}</h1>
              <p className="text-zinc-400 mt-1">{t("subtitle")}</p>
            </div>
            <div className="flex items-center gap-3">
              {error && <span className="text-xs text-red-400">{error}</span>}
              <button
                onClick={handleSave}
                disabled={saving}
                className={`flex items-center gap-1.5 px-4 py-2 text-sm rounded-md transition-colors ${
                  saved
                    ? "bg-green-600/20 text-green-400"
                    : savedLocally
                      ? "bg-amber-600/20 text-amber-400"
                      : "bg-brand-600 hover:bg-brand-500 text-white disabled:bg-zinc-700"
                }`}
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {saving ? t("saving") : saved ? t("saved") : savedLocally ? "已本地缓存" : t("save")}
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-border mb-6">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm border-b-2 transition-colors ${
                    activeTab === tab.key
                      ? "border-brand-500 text-brand-400"
                      : "border-transparent text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* ── Appearance ── */}
          {activeTab === "appearance" && (
            <div className="bg-surface-elevated rounded-lg border border-border p-5">
              <h2 className="text-sm font-semibold text-zinc-200 mb-4 flex items-center gap-2">
                <Monitor className="w-4 h-4" />
                {t("theme")}
              </h2>
              <div className={fieldCls}>
                <div className="flex gap-3">
                  {(["dark", "light"] as const).map((theme) => (
                    <button
                      key={theme}
                      onClick={() => update("theme", theme)}
                      className={`flex-1 py-3 rounded-md border text-sm transition-colors ${
                        s.theme === theme
                          ? "border-brand-500 bg-brand-600/10 text-brand-400"
                          : "border-border bg-zinc-900 text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      {t(`theme${theme.charAt(0).toUpperCase() + theme.slice(1)}`)}
                    </button>
                  ))}
                </div>
              </div>

              <h2 className="text-sm font-semibold text-zinc-200 mb-4 mt-6 flex items-center gap-2">
                <Palette className="w-4 h-4" />
                {t("accentColor")}
              </h2>
              <div className={fieldCls}>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={s.accentColor}
                    onChange={(e) => update("accentColor", e.target.value)}
                    className="w-10 h-10 rounded cursor-pointer border border-border bg-transparent"
                  />
                  <input
                    type="text"
                    value={s.accentColor}
                    onChange={(e) => update("accentColor", e.target.value)}
                    className={inputCls}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ── Model ── */}
          {activeTab === "model" && (
            <div className="bg-surface-elevated rounded-lg border border-border p-5">
              {/* Model type selector */}
              <h2 className="text-sm font-semibold text-zinc-200 mb-4 flex items-center gap-2">
                <Brain className="w-4 h-4" />
                {t("modelType")}
              </h2>
              <div className={fieldCls}>
                <div className="flex gap-3">
                  {([
                    { key: "local" as const, icon: Cpu, label: t("modelTypeLocal") },
                    { key: "online" as const, icon: Cloud, label: t("modelTypeOnline") },
                  ]).map((option) => {
                    const Icon = option.icon;
                    return (
                      <button
                        key={option.key}
                        onClick={() => update("modelType", option.key)}
                        className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-md border text-sm transition-colors ${
                          s.modelType === option.key
                            ? "border-brand-500 bg-brand-600/10 text-brand-400"
                            : "border-border bg-zinc-900 text-zinc-400 hover:text-zinc-200"
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* ── Local model config ── */}
              {s.modelType === "local" && (
                <div>
                  <p className="text-xs text-zinc-500 mb-4">{t("localLlmDesc")}</p>

                  <div className={fieldCls}>
                    <label className={labelCls}>{t("apiUrl")}</label>
                    <div className="flex items-center gap-2">
                      <Globe className="w-4 h-4 text-zinc-500" />
                      <input
                        type="text"
                        value={s.localLlmUrl}
                        onChange={(e) => update("localLlmUrl", e.target.value)}
                        placeholder="http://localhost:11434"
                        className={inputCls + " flex-1"}
                      />
                    </div>
                  </div>

                  <div className={fieldCls}>
                    <label className={labelCls}>{t("modelName")}</label>
                    <input
                      type="text"
                      value={s.localLlmModel}
                      onChange={(e) => update("localLlmModel", e.target.value)}
                      placeholder="llama3"
                      className={inputCls}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className={fieldCls}>
                      <label className={labelCls}>
                        {t("temperature")} <span className="text-zinc-600">({t("temperatureHint")})</span>
                      </label>
                      <input
                        type="number"
                        min={0}
                        max={2}
                        step={0.1}
                        value={s.localLlmTemperature}
                        onChange={(e) =>
                          update("localLlmTemperature", parseFloat(e.target.value) || 0)
                        }
                        className={inputCls}
                      />
                    </div>
                    <div className={fieldCls}>
                      <label className={labelCls}>{t("maxTokens")}</label>
                      <input
                        type="number"
                        min={1}
                        max={200000}
                        step={1000}
                        value={s.localLlmMaxTokens}
                        onChange={(e) =>
                          update("localLlmMaxTokens", parseInt(e.target.value) || 8192)
                        }
                        className={inputCls}
                      />
                    </div>
                  </div>

                  <div className="mt-2 p-3 bg-zinc-800/50 rounded-md border border-border">
                    <p className="text-[10px] text-zinc-500">
                      {t("localLlmHint")}
                    </p>
                  </div>
                </div>
              )}

              {/* ── Online model config ── */}
              {s.modelType === "online" && (
                <div>
                  <p className="text-xs text-zinc-500 mb-4">{t("onlineLlmDesc")}</p>

                  <div className={fieldCls}>
                    <label className={labelCls}>{t("provider")}</label>
                    <select
                      value={s.onlineLlmProvider}
                      onChange={(e) => update("onlineLlmProvider", e.target.value)}
                      className={inputCls}
                    >
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="deepseek">DeepSeek</option>
                      <option value="zhipu">智谱 AI</option>
                      <option value="custom">自定义 (OpenAI 兼容)</option>
                    </select>
                  </div>

                  <div className={fieldCls}>
                    <label className={labelCls}>{t("apiKey")}</label>
                    <div className="flex items-center gap-2">
                      <Key className="w-4 h-4 text-zinc-500" />
                      <input
                        type="password"
                        value={s.onlineLlmApiKey}
                        onChange={(e) => update("onlineLlmApiKey", e.target.value)}
                        placeholder="sk-..."
                        className={inputCls + " flex-1"}
                      />
                    </div>
                  </div>

                  <div className={fieldCls}>
                    <label className={labelCls}>{t("baseUrl")}</label>
                    <div className="flex items-center gap-2">
                      <Globe className="w-4 h-4 text-zinc-500" />
                      <input
                        type="text"
                        value={s.onlineLlmBaseUrl}
                        onChange={(e) => update("onlineLlmBaseUrl", e.target.value)}
                        placeholder="https://api.openai.com/v1"
                        className={inputCls + " flex-1"}
                      />
                    </div>
                  </div>

                  <div className={fieldCls}>
                    <label className={labelCls}>{t("modelName")}</label>
                    <input
                      type="text"
                      value={s.onlineLlmModel}
                      onChange={(e) => update("onlineLlmModel", e.target.value)}
                      placeholder="gpt-4o"
                      className={inputCls}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className={fieldCls}>
                      <label className={labelCls}>
                        {t("temperature")} <span className="text-zinc-600">({t("temperatureHint")})</span>
                      </label>
                      <input
                        type="number"
                        min={0}
                        max={2}
                        step={0.1}
                        value={s.onlineLlmTemperature}
                        onChange={(e) =>
                          update("onlineLlmTemperature", parseFloat(e.target.value) || 0)
                        }
                        className={inputCls}
                      />
                    </div>
                    <div className={fieldCls}>
                      <label className={labelCls}>{t("maxTokens")}</label>
                      <input
                        type="number"
                        min={1}
                        max={200000}
                        step={1000}
                        value={s.onlineLlmMaxTokens}
                        onChange={(e) =>
                          update("onlineLlmMaxTokens", parseInt(e.target.value) || 8192)
                        }
                        className={inputCls}
                      />
                    </div>
                  </div>

                  <div className="mt-2 p-3 bg-zinc-800/50 rounded-md border border-border">
                    <p className="text-[10px] text-zinc-500 flex items-center gap-1">
                      <Zap className="w-3 h-3" />
                      {t("onlineLlmHint")}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
