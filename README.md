# Tapo Plus

Integração para Home Assistant que traz das câmeras Tapo o que o app mostra e o
[Tapo: Cameras Control](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control)
não traz. Foi feita a partir da engenharia reversa do app Tapo 3.22.304
(`com.tplink.iot`). Ela complementa o tapo_control e não o substitui. Stream,
PTZ e os switches continuam lá, e as entidades daqui entram no mesmo dispositivo
(o vínculo é pelo MAC).

## O que entra

**Local** (polling de 60 s, 2 a 3 requisições `multipleRequest` por ciclo):

| Entidade | Origem no firmware |
|---|---|
| Último evento, tipo do último evento | `getLastAlarmInfo` |
| Eventos (24h), com contagem por tipo e os 10 últimos | `searchDetectionList` |
| Último movimento, última pessoa | `searchDetectionList` (`alarm_type` 2 / 6) |
| Gravações hoje, tempo gravado hoje | `searchVideoOfDay` |
| Modo de gravação (contínua / só eventos / desligado) | `getRecordPlan` |
| Cartão SD usado, gravação mais antiga, retenção em dias | `getSdCardStatus` |
| Resolução, bitrate, codec e fps do vídeo | `getVideoQualities` / `getVideoCapability` |
| Sinal Wi‑Fi (dBm), IP/gateway/DNS, conectada desde | `getConnectionType` / `getDeviceIpAddress` |
| Desvio do relógio da câmera | `getClockStatus` / `getTimezone` |
| Estado do firmware, auto‑update e horário | `getFirmwareUpdateStatus` / `getFirmwareAutoUpgradeConfig` |
| Tipos de notificação ativos (push × alarme, sensibilidades) | `getMsgPushEventList` / `getAlertEventType` |
| Problema no SD, UPnP, ONVIF TLS, compatibilidade com terceiros | binários de diagnóstico |

**Controles** (todos testados numa C200: grava → relê → reverte):

| Tipo | Entidades |
|---|---|
| Câmera | Vídeo HD (`stream1`) e SD (`stream2`, desativada por padrão) via RTSP, snapshot por ffmpeg |
| Ao vivo (5 s) | Movimento, Pessoa, Evento em andamento (evento aberto no `searchDetectionList`) |
| Switch | privacidade, detecção de movimento/pessoa/adulteração/choro (e veículo/pet onde houver), rastreamento automático, rastreamento inteligente (se suportado), alarme automático + som + luz, notificações + com imagem, notificar e disparar alarme **por tipo de evento**, gravar no SD, gravação em loop, gravar áudio, microfone/alto-falante mudo, cancelamento de ruído, LED, inverter imagem, correção de distorção, data na imagem, zonas de privacidade, auto-update de firmware, compatibilidade com terceiros, patrulha |
| Number | sensibilidade de movimento/pessoa/adulteração/choro, volume do alto-falante e do microfone, brilho, passo do PTZ |
| Select | visão noturna (auto/ligada/desligada), frequência da luz, volume e som da sirene, ir para posição salva |
| Botões | reiniciar, formatar SD, calibrar PTZ, mover ↑ ↓ ← → |
| Sirene / Update | alarme manual; firmware (instala pela câmera) |

As credenciais RTSP (conta da câmera) vêm do tapo_control automaticamente quando a
câmera foi importada de lá.

**Nuvem** (opcional, uma entrada por conta TP-Link, polling de 2 min):
câmera online, última notificação (com título, texto e URL da imagem), contagem
de notificações em 24h e firmware que a nuvem informa.

## Instalação

Copie `custom_components/tapo_plus` para `/config/custom_components/` (ou instale
pelo HACS como repositório customizado) e reinicie o HA. Depois vá em **Adicionar
integração → Tapo Plus**:

- **Usar câmera do Tapo: Cameras Control**: reaproveita o IP e a senha que já estão cadastrados lá.
- **Adicionar câmera manualmente**: informe o IP e a senha da **conta TP-Link**.
- **Adicionar conta da nuvem TP-Link**: e-mail e senha. Se a TP-Link pedir, ela manda um código por e-mail (MFA).

> ⚠️ O login local é `admin` + a senha da conta TP-Link. O usuário/senha de RTSP
> não servem. Cada senha errada conta para o bloqueio de 30 minutos da câmera
> ("Temporary Suspension"). Se der erro de autenticação, a integração para de
> tentar e pede reautenticação.

## Limitações conhecidas

- Na C200, contraste, saturação, nitidez, WDR, backlight e dehaze aparecem no `get`, mas o firmware recusa gravar (`-40209`). O app também não oferece esses ajustes.
- A sirene usa `doManualAlarm` e, se falhar, o formato legado `{"method":"do","msg_alarm":{"manual_msg_alarm":…}}`. Não foi disparada em teste.
- Ainda não há navegação/sincronização das gravações do SD (media source do tapo_control).

## Protocolo (o que a RE encontrou)

### Local

- Transporte: `securePassthrough` na porta 443, via [pytapo](https://github.com/JurajNyiri/pytapo).
- Catálogo completo: 807 métodos do enum `libtapocameranetwork/model/Method`, em [`docs/methods.tsv`](docs/methods.tsv).
- Formato dos parâmetros, extraído de `mv0/zk.java`: `{"<module>": {"name": ["<section>"]}}`, ou `{"<module>": {"table": [...]}}`, ou `{"<module>": {"<ação>": {}}}`. Veja [`docs/request-shapes.json`](docs/request-shapes.json).
- O que uma C200 v5 realmente responde: [`docs/c200-supported.md`](docs/c200-supported.md). São 73 de 248 getters.
- Códigos de `alarm_type` (enum `PlayBackEventType`): 1 timing, 2 motion, 3 tamper, 4 linecross, 5 area intrusion, 6 person, 7 baby cry, 8 vehicle, 9 pet, 11 bark, 12 meow, 13 glass, 14 smoke, 15/16 package, 17/18 doorbell, 33 animal, 36 CO, entre outros (ver `const.py`).
- Escrita: `set<X> {módulo:{seção:{campo:valor}}}`, o mesmo formato do get. Particularidades da C200: `setDayNightModeConfig` exige `"chn_id": ["1"]`; `setFirmwareAutoUpgradeConfig` exige `time` + `random_range`; o brilho só é aceito por `setImageLumaConfig`; e a frequência da luz só por `setLightFrequencyInfo`.
- No `frame_rate`, os 16 bits baixos são o fps (`65551` = `0x1000F` = 15 fps).

### Nuvem (API v2)

- Base `https://n-wap.i.tplinkcloud.com` → `POST /api/v2/account/getAccountStatusAndUrl` devolve `appServerUrl`. Depois vêm `/api/v2/account/login`, `/api/v2/common/getDeviceListByPage`, `/api/v2/common/getAppNotificationByPage` (central de notificações; só funciona com `direction: "asc"` a partir de `indexTime` em ms — `desc` volta vazio; `getDeviceMsgsByPage` existe mas o app não usa e volta sempre vazio) e `/api/v2/common/passthrough` (manda métodos da câmera pela nuvem).
- Assinatura (interceptor `m7/r`):
  `Content-MD5 = base64(md5(body))` e
  `X-Authorization: Timestamp=9999999999, Nonce=<uuid>, AccessKey=4d11b6b9d5ea4d19a829adbb9714b057, Signature=hex(HMAC-SHA1(6ed7d97f3e73467f8a5bab90b577ba4c, md5 + "\n9999999999\n" + nonce + "\n" + path))`.
  Sem assinatura, a resposta é `-10303 Signature params invalid`.
- Query (interceptor `m7/q`): `appName, appVer, netType, termID, ospf, brand, locale[, token]`.
- TLS: a TP-Link usa CA própria. A raiz em `tplink_cloud_ca.pem` é a mesma que o app embarca em `mergedCA.pem`.
- Token expirado: `-20651` / `-20675` (`libcloud/utils/b.java`). Nesse caso a integração faz login de novo.
- MFA: `getEmailVC4TerminalMFA` → `checkMFACodeAndLogin {mfaProcessId, code, mfaType:1, terminalBindEnabled:true}`.

## Teste

```sh
uv run --python 3.14 --with homeassistant --with numpy --with ha-ffmpeg --with PyTurboJPEG --with av python tests/check_sensors.py
```

O teste roda todos os sensores contra uma resposta real (anonimizada) de uma C200.
