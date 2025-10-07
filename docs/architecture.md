# アーキテクチャ概要

本ドキュメントは `requirements.md` に記載された機能要件・非機能要件を満たすためのシステム構成を整理したものです。本リポジトリではまずドメインロジック層を Python で実装し、Windows ネイティブなキャプチャおよびキー送出は将来のネイティブレイヤー（C# / Rust など）に委譲します。

## 全体構成

```
+-------------------+        +---------------------+
|  Windows Native    |        |  Core Domain (Py)   |
|  Integrations      |<-----> |  (本リポジトリ)       |
|  - Win32 Capture   |        |  - 設定管理           |
|  - SendInput       |        |  - セッション制御     |
|  - Hotkey Hook     |        |  - 出力ファイル生成   |
+-------------------+        +---------------------+
            ^                           |
            |                           v
      GUI (WPF 等)                CLI / テスト
```

- **GUI / ネイティブ層**: Windows API を利用してスクリーンショット取得、ホットキー監視、キー送出を行う。Python 側のサービスインターフェイスを実装する。
- **Core Domain**: 要件で定義されたシナリオを成立させるための状態管理とワークフロー制御を担う。本リポジトリで実装。
- **CLI / テスト**: 自動テストによりドメインロジックを検証。将来的には CLI でバッチ実行も可能。

## モジュール構成

| モジュール | 役割 |
| --- | --- |
| `scu.config` | 設定スキーマと JSON 永続化、テンプレート管理 |
| `scu.output` | 保存先ディレクトリの管理、ファイル命名、セッションフォルダ生成 |
| `scu.session` | 実行中セッションの状態管理、一時停止・再開・停止の状態遷移 |
| `scu.pipeline` | キャプチャ・キー送出・待機ロジックを指揮し、進捗を更新 |
| `scu.interfaces` | Windows ネイティブ層が実装すべき抽象インターフェイス |
| `scu.events` | UI やログ用のイベント通知モデル |

## 主なクラスと責務

### 設定 (`scu.config`)
- `CaptureTarget`, `WaitStrategy`, `HotkeyConfig` などの列挙/データクラス。
- `AppConfig` が全体設定を一元的に保持。
- `ConfigRepository` が JSON ファイルの保存/読込/テンプレート管理を行う。

### セッション (`scu.session`)
- `SessionState` が `idle` / `running` / `paused` / `stopped` を表す。
- `SessionController` が状態遷移、進捗更新、エラー停止を担う。

### パイプライン (`scu.pipeline`)
- `CaptureService`, `InputService`, `WaitService` の抽象を受け取り、1 ステップ（撮影＋キー送出）を実行。
- 処理順序 (`shot-first` / `key-first`) や待機方法を設定で制御。
- 画面変化待ちとタイムアウトのロジックを持つ。

### 出力 (`scu.output`)
- `SessionPathManager` が保存先の検証、セッションディレクトリ生成、ファイル名採番を担当。
- 重複検知用のハッシュ計算を支援。

## シーケンス概要

1. GUI からユーザー設定が `AppConfig` として渡される。
2. `SessionController` が `SessionPathManager` を介して保存先を初期化。
3. `SessionController` が `Pipeline` を開始し、回数や時間制限に応じてループ。
4. 各ステップで `Pipeline` は処理順序に従って `CaptureService` / `InputService` を呼び出し、`WaitService` を利用してディレイまたは画面変化待ちを実施。
5. 進捗は `ProgressEvent` として購読者（GUI、ログ）に通知される。
6. ホットキー等で `pause` / `resume` / `stop` が呼び出されると `SessionController` が状態遷移し、`Pipeline` へ伝播。

## 今回実装範囲

- Python ベースのドメインモデル・コントローラの初期実装。
- JSON 設定保存・読込、セッションディレクトリ生成、ファイル名命名規則、進捗イベントモデル。
- Windows API への具体実装はモックに留め、テスト可能な構造を提供。

## 今後のステップ

- Windows 向けネイティブ実装（C# or Rust）で `CaptureService` / `InputService` を提供。
- GUI 実装（WPF / Avalonia 等）で状態表示、プレビュー、ホットキー設定を実現。
- 受入テスト (AT-01〜AT-10) を自動化するための統合テスト環境構築。
