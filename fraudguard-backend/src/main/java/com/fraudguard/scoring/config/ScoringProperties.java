package com.fraudguard.scoring.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "fraudguard.scoring")
public class ScoringProperties {

    private String pythonApiUrl;
    private int timeoutMs = 2000;

    public String getPythonApiUrl() {
        return pythonApiUrl;
    }

    public void setPythonApiUrl(String pythonApiUrl) {
        this.pythonApiUrl = pythonApiUrl;
    }

    public int getTimeoutMs() {
        return timeoutMs;
    }

    public void setTimeoutMs(int timeoutMs) {
        this.timeoutMs = timeoutMs;
    }
}
