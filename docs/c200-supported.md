# Getters testados numa C200 v5 (fw 1.5.7)

Varredura de todos os `get*` do app via `multipleRequest`, 30/10/2026.

## Respondem (73)

- `checkDiagnoseStatus`
- `getAESEncryptKey`
- `getAlertConfig`
- `getAlertEventType`
- `getAlertPlan`
- `getAlertTypeList`
- `getAppComponentList`
- `getBCDConfig`
- `getCircularRecordingConfig`
- `getClockStatus`
- `getCloudConfig`
- `getConfigSSID`
- `getConnectionType`
- `getCoverConfig`
- `getDayNightModeConfig`
- `getDetectionMode`
- `getDeviceInfo`
- `getDeviceIpAddress`
- `getDnSwitchModeCapability`
- `getDnSwitchModeConfig`
- `getDstRule`
- `getFirmwareAutoUpgradeConfig`
- `getFirmwareUpdateStatus`
- `getGlobalDetectionRegion`
- `getHubStorage`
- `getImageLumaConfig`
- `getImageStyleCapability`
- `getImageStyleConfig`
- `getInfLampCapability`
- `getInfLampType`
- `getLastAlarmInfo`
- `getLdc`
- `getLedStatus`
- `getLensMaskConfig`
- `getMediaPSK`
- `getMsgPushConfig`
- `getMsgPushEventList`
- `getMsgPushPlan`
- `getNetworkInterfaces`
- `getNightVisionCapability`
- `getNightVisionModeConfig`
- `getOnvifSecurityCapability`
- `getOnvifSecurityConfig`
- `getOsd`
- `getOsdCapability`
- `getP2PSharePassword`
- `getPatrolAction`
- `getPatrolInfo`
- `getPatrolSchedule`
- `getPatrolStatus`
- `getPresetConfig`
- `getRecordPlan`
- `getRotationStatus`
- `getScanHubList`
- `getSdCardStatus`
- `getSmartTrackCapability`
- `getSmartTrackConfig`
- `getTamperDetectionConfig`
- `getTapoCareServiceList`
- `getTapoDetectionRegion`
- `getTargetTrackConfig`
- `getThirdAccount`
- `getThirdPartyCompatibility`
- `getTimezone`
- `getUpnpInfo`
- `getUpnpPsk`
- `getUserID`
- `getVideoCapability`
- `getVideoQualities`
- `getWhitelampCapability`
- `getWhitelampConfig`
- `getWhitelampStatus`
- `getWifiBackup`

## Não suportados (-40209 e afins) (175)

`get4gBackupCfg`, `getAbnormalPowerStatus`, `getAlarmConfig`, `getAlarmDetectionConfig`, `getAllChnInfo`, `getAntiTheftEnable`, `getAntiTheftStatus`, `getAovConfig`, `getApnConfig`, `getAppLdcID`, `getApproachDetectionConfig`, `getAudioConfig`, `getAutoAnswerContact`, `getAutoSw`, `getBabyLeaveDetectionConfig`, `getBabySleepDetectionConfig`, `getBabySleepDetectionSensitivityCapability`, `getBarkDetectionConfig`, `getBatteryCapability`, `getBatteryConfig`, `getBatteryPowerSave`, `getBatteryStatus`, `getBindedSensor`, `getBleObBasicInfo`, `getButtonConfig`, `getCalibratedParams`, `getCallLog`, `getCallStateInfo`, `getCaregiverDetectionConfig`, `getChargingMode`, `getChargingPrivacyMode`, `getChimeCtrlKey`, `getChimeCtrlList`, `getChimeRingPlan`, `getChn2CoverRegion`, `getCloudAccount`, `getCloudNetDiagnose`, `getConnectStatus`, `getCoverRegion`, `getDataTrafficLimit`, `getDataTrafficNotification`, `getDataTrafficOfYear`, `getDetectionConfig`, `getDevMgrCapability`, `getDeviceLanguage`, `getDeviceLanguageCapability`, `getDeviceListWithVideoRange`, `getDiagnoseMode`, `getDiagnoseStatus`, `getDisplayConfig`, `getDoorlockRecords`, `getDownloadState`, `getDualCamCapability`, `getDualCamLinkage`, `getExpressionDetectionConfig`, `getFaceDetectionConfig`, `getFaceNotificationConfig`, `getFacecoverDetectionConfig`, `getFastOnboardingList`, `getFirmwareCapability`, `getFirmwareUpdateProcess`, `getFloodlightCapability`, `getFloodlightConfig`, `getFloodlightDetEvtType`, `getFloodlightFadeEnable`, `getFloodlightPirTrigPlan`, `getFloodlightStatus`, `getForceWhitelampState`, `getFreqTriggerStatus`, `getGlassDetectionConfig`, `getHardDiskFormatStatus`, `getHardDiskStatus`, `getHoverDetectionCapability`, `getHoverDetectionConfig`, `getHprDetectionConfig`, `getHubAlarmStatus`, `getHubRingPlan`, `getHubRingPlay`, `getHubRingSoundConfig`, `getHubRingStatus`, `getImageCapability`, `getInfo4g`, `getIntrusionDetectionConfig`, `getIntrusionDetectionRegion`, `getIpConflictStatus`, `getIpManagerConfig`, `getLedColor`, `getLightFrequencyCapability`, `getLinecrossingDetectionConfig`, `getLinecrossingDetectionRegion`, `getLinkageTargetCapability`, `getLockCapability`, `getManualAlarm`, `getManualAlarmStatus`, `getMarkerBoxConfig`, `getMeowDetectionConfig`, `getMobileTrafficData`, `getMotorAngleRange`, `getMotorFov`, `getMusicConfig`, `getMusicList`, `getNVRDstRule`, `getNameplateLightConfig`, `getNightModePlan`, `getNightlightStatus`, `getOfflineSwitchWiFi`, `getOneClickCallContact`, `getOutdoorMode`, `getPackageDetectionConfig`, `getPackageDetectionRecommendRegion`, `getPackageDetectionRegion`, `getPanoramicVideoSchedule`, `getPanoramicVideoStatus`, `getPanoramicView`, `getPersonDetectionConfig`, `getPetDetectionConfig`, `getPirDetCapability`, `getPirDetConfig`, `getPirSensitivity`, `getPtzFollowPointingSetting`, `getPtzInfo`, `getQuickRespCapability`, `getQuickRespLanguage`, `getQuickRespList`, `getROIClarity`, `getROIClarityZone`, `getROIClarityZoom`, `getRadarBasicInfo`, `getRadarCapability`, `getReboot`, `getRingPlay`, `getRingSoundConfig`, `getRingStatus`, `getSafeFenceDetectionConfig`, `getSafeFenceRegion`, `getScreen24HourClockConfig`, `getScreenFollowConfig`, `getScreenTextModeConfig`, `getSdCardFormatStatus`, `getSensorCapability`, `getSirenStatus`, `getSleepDataOfMultipleDays`, `getSleepStatisticsConfig`, `getSmartAECapability`, `getSmartAEConfig`, `getSmartRespConfig`, `getSmartWhiteLampConfig`, `getSnoozeAlertStatus`, `getSplendidMomentBaby`, `getSplendidMomentStorage`, `getSplendidMomentSwitch`, `getStatisticsDataOfMultipleDays`, `getStreamDiagnose`, `getSwNetDev`, `getSwitchLockInfo`, `getTapoCareUploadResult`, `getThirdPartyCamera`, `getTimeAlarmCapbability`, `getTimeAlarmParams`, `getTimeAlarmSysAudio`, `getTimeDiagnose`, `getTrackBoxConfig`, `getTrafficPlanCfg`, `getTssScanDeviceList`, `getUpnpCapability`, `getVehicleDetectionConfig`, `getVolumeSetting`, `getVolumeSettingCapability`, `getWakeUpConfig`, `getWallpaperDisplay`, `getWallpaperDisplayTime`, `getWallpaperList`, `getWeatherInfo`, `getWebrtcCapability`, `getWtlDnSwitchModeConfig`
