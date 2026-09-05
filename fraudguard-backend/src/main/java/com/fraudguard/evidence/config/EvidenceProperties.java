package com.fraudguard.evidence.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "fraudguard.evidence")
@Data
public class EvidenceProperties {
    private int hotCacheTtlDays = 15;
    private int coldRetentionDays = 120;
    private String purgeCron;
}
