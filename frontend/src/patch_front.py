import re

with open('main.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update website inner image selector
target1 = '''      const imgModels = ["gemini", "gemini_flash_lite", "grok"];
      const imgModelInfo: Record<string, {name: string, color: string}> = {
        "gemini": { name: "Imagen 4", color: "0, 200, 255" },
        "gemini_flash_lite": { name: "Gemini 3.1 Flash Lite", color: "0, 200, 255" },
        "grok": { name: "xAI Grok", color: "160, 60, 255" },
      };'''

replacement1 = '''      const imgModels = ["openai", "gemini", "gemini_flash_lite", "grok"];
      const imgModelInfo: Record<string, {name: string, color: string}> = {
        "openai": { name: "DALL-E 3", color: "0, 166, 126" },
        "gemini": { name: "Imagen 4", color: "0, 200, 255" },
        "gemini_flash_lite": { name: "Gemini 3.1 Flash Lite", color: "0, 200, 255" },
        "grok": { name: "xAI Grok", color: "160, 60, 255" },
      };'''

content = content.replace(target1, replacement1)

# 2. Update pure image selector
target2 = '''  const models = ["gemini", "gemini_flash_lite", "grok"];
  const modelInfo: Record<string, {name: string, color: string}> = {
    "gemini": { name: "Imagen 4", color: "0, 200, 255" },
    "gemini_flash_lite": { name: "Gemini 3.1 Flash Lite", color: "0, 200, 255" },
    "grok": { name: "xAI Grok", color: "160, 60, 255" },
  };'''

replacement2 = '''  const models = ["openai", "gemini", "gemini_flash_lite", "grok"];
  const modelInfo: Record<string, {name: string, color: string}> = {
    "openai": { name: "DALL-E 3", color: "0, 166, 126" },
    "gemini": { name: "Imagen 4", color: "0, 200, 255" },
    "gemini_flash_lite": { name: "Gemini 3.1 Flash Lite", color: "0, 200, 255" },
    "grok": { name: "xAI Grok", color: "160, 60, 255" },
  };'''

content = content.replace(target2, replacement2)

with open('main.ts', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch frontend image models applied")
