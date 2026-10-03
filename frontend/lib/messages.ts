/** 画面文言（設計仕様書 12.1／9.2）。テスト T-067 で一致を確認する。 */
export const MSG = {
  productNotFound: "商品がマスタ未登録です。商品コードを確認してください。",
  memberNotFound: "会員IDが見つかりません。再入力するか、非会員を選択してください。",
  emptyCart: "商品を1件以上追加してください。",
  sessionExpired: "セッションの有効期限が切れました。再度ログインしてください。",
  saveFailed: "購入を確定できませんでした。再度お試しください。",
  authFailed: "IDまたはパスワードが正しくありません",
  productCodeFormat: "商品コードは13桁の数字で入力してください。",
  memberIdFormat: "会員IDは「M」と6桁の数字で入力してください（例：M000123）。",
  quantityCap: "1つの商品は99個まで追加できます。",
  productChanged: "購入リストに販売できない商品が含まれています。商品を確認してください。",
  salesModeRequired: "取引区分（店内／持ち帰り）を選んでください。",
  network: "サーバーに接続できません。通信状態を確認してください。",
  passwordLength: "パスワードは8〜64文字で入力してください。",
} as const;
