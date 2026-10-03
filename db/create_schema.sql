-- =====================================================================
-- 新規スキーマ（データベース）とアプリ用ユーザーの作成
-- 管理者ユーザーで1回だけ実行する。<...> は自分の値に置き換えること（このファイルにパスワードを書いてコミットしない）。
--
--   mysql -h <server>.mysql.database.azure.com -u <admin> -p --ssl-mode=REQUIRED < db/create_schema.sql
-- =====================================================================
CREATE DATABASE IF NOT EXISTS pos_app
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_bin;

-- アプリ用ユーザーは最小権限（DDL 権限なし）。マイグレーションは管理者ユーザーで実行する。
CREATE USER IF NOT EXISTS 'pos_app_user'@'%' IDENTIFIED BY '<STRONG_PASSWORD>';
GRANT SELECT, INSERT, UPDATE, DELETE ON pos_app.* TO 'pos_app_user'@'%';
FLUSH PRIVILEGES;
