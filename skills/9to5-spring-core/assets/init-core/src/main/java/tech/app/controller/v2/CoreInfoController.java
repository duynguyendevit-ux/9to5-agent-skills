package tech.app.controller.v2;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import tech.app.model.CoreInfo;
import tech.app.usecase.CoreInfoUseCaseService;
import tech.outsource.core.configurations.controller.v2.V2API;
import tech.outsource.core.model.v2.ValueResponse;

@RestController
@RequestMapping("/v2/api/core")
public class CoreInfoController implements V2API {
    private final CoreInfoUseCaseService service;

    public CoreInfoController(CoreInfoUseCaseService service) {
        this.service = service;
    }

    @GetMapping("/info")
    public ValueResponse<CoreInfo> info() {
        return ValueResponse.of(service.getInfo());
    }
}
