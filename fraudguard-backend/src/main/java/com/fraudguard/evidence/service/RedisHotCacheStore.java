package com.fraudguard.evidence.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fraudguard.evidence.model.EvidenceSnapshot;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import java.time.Duration;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

@Service("hotCacheStore")
@RequiredArgsConstructor
@Slf4j
public class RedisHotCacheStore implements HotCacheStore {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private static final String KEY_PREFIX = "evidence:";

    private String getKey(long transactionId) {
        return KEY_PREFIX + transactionId;
    }

    @Override
    public void put(long transactionId, EvidenceSnapshot snapshot, Duration ttl) {
        try {
            String key = getKey(transactionId);
            String json = objectMapper.writeValueAsString(snapshot);
            redisTemplate.opsForValue().set(key, json, ttl);
        } catch (Exception e) {
            log.warn("Failed to write to Redis hot cache for transactionId {}", transactionId, e);
        }
    }

    @Override
    public Optional<EvidenceSnapshot> get(long transactionId) {
        try {
            String key = getKey(transactionId);
            String json = redisTemplate.opsForValue().get(key);
            if (json != null) {
                return Optional.of(objectMapper.readValue(json, EvidenceSnapshot.class));
            }
        } catch (Exception e) {
            log.warn("Failed to read from Redis hot cache for transactionId {}", transactionId, e);
        }
        return Optional.empty();
    }

    @Override
    public void update(long transactionId, EvidenceSnapshot snapshot) {
        try {
            String key = getKey(transactionId);
            Long expireSecs = redisTemplate.getExpire(key, TimeUnit.SECONDS);
            if (expireSecs != null && expireSecs > 0) {
                String json = objectMapper.writeValueAsString(snapshot);
                redisTemplate.opsForValue().set(key, json, Duration.ofSeconds(expireSecs));
            }
        } catch (Exception e) {
            log.warn("Failed to update Redis hot cache for transactionId {}", transactionId, e);
        }
    }
}
