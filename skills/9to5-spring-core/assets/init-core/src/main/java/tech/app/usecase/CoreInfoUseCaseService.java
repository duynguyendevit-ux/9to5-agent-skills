package tech.app.usecase;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import tech.app.model.CoreInfo;

@Service
public class CoreInfoUseCaseService {
    private final String serviceName;

    public CoreInfoUseCaseService(@Value("${spring.application.name}") String serviceName) {
        this.serviceName = serviceName;
    }

    public CoreInfo getInfo() {
        return new CoreInfo(serviceName);
    }
}
