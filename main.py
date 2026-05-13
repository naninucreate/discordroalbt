import discord
from discord.ext import commands
from discord import app_commands
import os
from flask import Flask
from threading import Thread

# ==========================================
# 1. Flask Webサーバー (Renderのスリープ防止用)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web():
    # Renderが指定するポートで待機
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ==========================================
# 2. 永続的なボタンの設定
# ==========================================
class PersistentRoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str):
        # custom_idをロールIDごとに固定することで再起動後も識別可能にする
        super().__init__(
            label=label,
            style=discord.ButtonStyle.success,
            custom_id=f"persistent_role_id_{role_id}"
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        # サーバーからロールを取得
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("エラー：ロールが見つかりませんでした。", ephemeral=True)

        # ロールの付け外し判定
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"✅ {role.name} を外しました。", ephemeral=True)
        else:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✨ {role.name} を付与しました！", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("エラー：Botの権限不足です。ロールの順序を確認してください。", ephemeral=True)

# ==========================================
# 3. Bot本体の定義
# ==========================================
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True # ロール操作に必須
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Bot起動時に実行される処理"""
        # 重要：再起動後にボタンを再認識させるためのリスナー登録
        # 空のViewでも、Interaction（custom_id）を受け取るとボタン側が反応します
        self.add_view(discord.ui.View(timeout=None))
        
        # スラッシュコマンドを同期
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")

bot = MyBot()

@bot.tree.command(name="setup_role", description="再起動しても動くロールパネルを設置します")
@app_commands.describe(role="付与したいロールを選択")
@app_commands.checks.has_permissions(manage_roles=True)
async def setup_role(interaction: discord.Interaction, role: discord.Role):
    # Botの権限チェック
    if interaction.guild.me.top_role <= role:
        return await interaction.response.send_message("エラー：Botのロール順位を対象ロールより上に上げてください。", ephemeral=True)

    embed = discord.Embed(
        title="ロールパネル",
        description=f"下のボタンを押すと {role.mention} を受け取れます。",
        color=role.color if role.color.value != 0 else discord.Color.blue()
    )

    # 永続的なViewを作成（timeout=None）
    view = discord.ui.View(timeout=None)
    view.add_item(PersistentRoleButton(role.id, f"{role.name} を付ける/外す"))

    await interaction.response.send_message(embed=embed, view=view)

# ==========================================
# 4. 実行
# ==========================================
if __name__ == "__main__":
    # Webサーバー起動（スレッドを分ける）
    keep_alive()
    
    # 環境変数からトークンを読み込む
    token = os.environ.get("DISCORD_BOT_TOKEN")
    
    if token:
        try:
            bot.run(token)
        except Exception as e:
            print(f"Bot起動エラー: {e}")
    else:
        print("エラー：環境変数 'DISCORD_BOT_TOKEN' が設定されていません。")
