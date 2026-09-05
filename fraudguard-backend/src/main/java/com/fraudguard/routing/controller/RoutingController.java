package com.fraudguard.routing.controller;

import com.fraudguard.routing.config.RoutingProperties;
import com.fraudguard.routing.config.TierThresholdConfig;
import com.fraudguard.routing.model.ScoredTransaction;
import com.fraudguard.routing.model.TierAssignment;
import com.fraudguard.routing.service.ThresholdRefreshService;
import com.fraudguard.routing.service.TierRouterServiceImpl;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.time.Duration;
import java.util.List;

@RestController
@RequestMapping("/api/v1/routing")
public class RoutingController {

    private final TierRouterServiceImpl routerService;
    private final ThresholdRefreshService refreshService;
    private final RoutingProperties properties;

    @Autowired
    public RoutingController(TierRouterServiceImpl routerService, ThresholdRefreshService refreshService, RoutingProperties properties) {
        this.routerService = routerService;
        this.refreshService = refreshService;
        this.properties = properties;
    }

    @PostMapping("/assign")
    public TierAssignment assign(@RequestBody ScoredTransaction transaction) {
        TierThresholdConfig config = refreshService.getCurrentConfig();
        TierAssignment assignment = routerService.assignTier(transaction, config);
        return routerService.save(assignment);
    }

    @PostMapping("/assign/batch")
    public List<TierAssignment> assignBatch(@RequestBody List<ScoredTransaction> transactions) {
        TierThresholdConfig config = refreshService.getCurrentConfig();
        return routerService.assignTierBatch(transactions, config);
    }

    @GetMapping("/config")
    public TierThresholdConfig getConfig() {
        return refreshService.getCurrentConfig();
    }

    @GetMapping("/config/stale")
    public boolean isConfigStale() {
        TierThresholdConfig config = refreshService.getCurrentConfig();
        return refreshService.isConfigStale(config, Duration.ofHours(properties.getStalenessMaxHours()));
    }
}
