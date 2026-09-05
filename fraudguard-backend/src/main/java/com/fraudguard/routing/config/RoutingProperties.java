package com.fraudguard.routing.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "fraudguard.routing")
public class RoutingProperties {
    
    private int stalenessMaxHours = 168;
    private String refreshCron;

    public int getStalenessMaxHours() {
        return stalenessMaxHours;
    }

    public void setStalenessMaxHours(int stalenessMaxHours) {
        this.stalenessMaxHours = stalenessMaxHours;
    }

    public String getRefreshCron() {
        return refreshCron;
    }

    public void setRefreshCron(String refreshCron) {
        this.refreshCron = refreshCron;
    }
}
