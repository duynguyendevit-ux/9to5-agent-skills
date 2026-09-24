package tech.app.configuration;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import tech.outsource.core.process.local.LocalProcessContextHolder;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class CoreContextCleanupFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        LocalProcessContextHolder.clearContext();
        try {
            chain.doFilter(request, response);
        } finally {
            LocalProcessContextHolder.clearContext();
        }
    }
}
